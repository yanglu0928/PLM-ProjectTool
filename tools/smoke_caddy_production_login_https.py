"""Run original real PG/Vault login assertions through pinned Caddy synthetic HTTPS.

Only a fresh loopback PG cluster, unique Vault target, and temporary TLS key are used.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import uvicorn

from audit_caddy_windows_offline_input import EXE_SHA256, audit as audit_caddy, digest
from smoke_caddy_same_origin_https import caddyfile, synthetic_certificate
from smoke_packaged_pg18_migration import _port, _run, verify_layout
from smoke_windows_pg18_sidecar import _start_pg_ctl


def _load_original() -> object:
    path = Path(__file__).resolve().parents[1] / "validation/aut-03-a07-p03-production-login/verify.py"
    spec = importlib.util.spec_from_file_location("_p21_original_login", path)
    if spec is None or spec.loader is None:
        raise ValueError("original login acceptance unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke(layout: Path, candidate: Path, caddy_inputs: Path, *,
          layout_verifier=verify_layout, boundary_audit=audit_caddy,
          caddy_relative: str = "expanded/caddy.exe", config_builder=caddyfile) -> dict:
    count = layout_verifier(layout, candidate)
    boundary_audit(caddy_inputs)
    caddy = caddy_inputs / caddy_relative
    if digest(caddy) != EXE_SHA256:
        raise ValueError("pinned Caddy executable changed")
    layout = layout.resolve(strict=True)
    frontend = layout / "app/frontend/dist"
    pg = layout / "runtime/pgsql/bin"
    port = _port()
    api_port, https_port = _port(), _port()
    while len({port, api_port, https_port}) != 3:
        api_port, https_port = _port(), _port()
    origin = f"https://localhost:{https_port}"
    original = _load_original()
    original.HOST, original.PORT = "127.0.0.1", port
    original_settings = original.BootstrapSettings
    actual_connect = original.connect
    actual_delete = original.delete_test_credential
    owned_databases: set[str] = set()
    deleted_targets: list[str] = []

    def tracked_connect(name: str):
        if name != "postgres":
            owned_databases.add(name)
        return actual_connect(name)

    def tracked_delete(target: str):
        actual_delete(target)
        deleted_targets.append(target)
    run = Path(tempfile.mkdtemp(prefix="plm-caddy-login-pg-", dir=tempfile.gettempdir()))
    data, log = run / "data", run / "postgresql.log"
    started = False
    network_counts = {"get": 0, "post": 0, "login_secure_cookie": 0,
                      "wrong_host_421": 0, "wrong_host_api_421": 0,
                      "wrong_origin_403": 0, "missing_csrf_403": 0}

    class HttpsClient:
        def __init__(self, app, **unused):
            self.app = app
            self.server = None
            self.thread = None
            self.sock = None
            self.caddy_process = None
            self.client = None
            self.temp = None

        def __enter__(self):
            try:
                self.temp = tempfile.TemporaryDirectory(prefix="plm-caddy-login-https-")
                root = Path(self.temp.name)
                cert, key, config = root / "cert.pem", root / "key.pem", root / "Caddyfile"
                synthetic_certificate(cert, key)
                config.write_text(config_builder(frontend, cert, key, api_port, https_port), encoding="ascii")
                validated = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                           capture_output=True, text=True, errors="replace", timeout=15)
                if validated.returncode:
                    raise ValueError("Caddy login test config invalid")
                self.sock = socket.socket()
                self.sock.bind(("127.0.0.1", api_port))
                self.sock.listen(128)
                self.server = uvicorn.Server(uvicorn.Config(
                    self.app, log_level="critical", access_log=False, proxy_headers=False,
                    lifespan="on", timeout_graceful_shutdown=5))
                self.thread = Thread(target=lambda: self.server.run(sockets=[self.sock]), daemon=False)
                self.thread.start()
                deadline = time.monotonic() + 20
                while not self.server.started:
                    if not self.thread.is_alive() or time.monotonic() > deadline:
                        raise RuntimeError("owned production API startup failed")
                    time.sleep(.05)
                env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PLM_")}
                self.caddy_process = subprocess.Popen([str(caddy), "run", "--config", str(config)],
                                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                      stderr=subprocess.DEVNULL, env=env)
                self.client = httpx.Client(base_url=origin, verify=str(cert), timeout=5,
                                           follow_redirects=False, trust_env=False)
                deadline = time.monotonic() + 20
                while True:
                    if self.caddy_process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("owned Caddy login boundary not ready")
                    try:
                        if self.client.get("/health/ready").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(.05)
                wrong = self.client.get("/", headers={"Host": "untrusted.example.test"})
                if wrong.status_code != 421:
                    raise ValueError("login HTTPS boundary accepted wrong Host")
                network_counts["wrong_host_421"] += 1
                wrong_api = self.client.post("/api/v1/auth/login", headers={
                    "Host": "untrusted.example.test"}, json={})
                if wrong_api.status_code != 421:
                    raise ValueError("login HTTPS API boundary accepted wrong Host")
                network_counts["wrong_host_api_421"] += 1
                return self
            except Exception:
                self.__exit__(None, None, None)
                raise

        def request(self, method, path, **kwargs):
            headers = dict(kwargs.pop("headers", {}))
            for key, value in list(headers.items()):
                if key.lower() == "origin" and value == "http://localhost":
                    headers[key] = origin
            response = self.client.request(method, path, headers=headers, **kwargs)
            network_counts[method.lower()] += 1
            if path == "/api/v1/auth/login" and response.status_code == 403:
                network_counts["wrong_origin_403"] += 1
            if path == "/api/v1/auth/login" and response.status_code == 200:
                cookie = response.headers.get("set-cookie", "")
                if not all(token in cookie for token in ("Secure", "HttpOnly", "SameSite=lax")):
                    raise ValueError("HTTPS login cookie lacks required flags")
                network_counts["login_secure_cookie"] += 1
                without_csrf = self.client.post("/api/v1/auth/session:renew", headers={"origin": origin})
                if without_csrf.status_code != 403 or "set-cookie" in without_csrf.headers:
                    raise ValueError("HTTPS session renew accepted missing CSRF")
                network_counts["missing_csrf_403"] += 1
            return response

        def get(self, path, **kwargs):
            return self.request("GET", path, **kwargs)

        def post(self, path, **kwargs):
            return self.request("POST", path, **kwargs)

        def __exit__(self, *unused):
            if self.client:
                self.client.close()
            if self.caddy_process:
                if self.caddy_process.poll() is None:
                    self.caddy_process.terminate()
                self.caddy_process.wait(timeout=15)
            if self.server:
                self.server.should_exit = True
            if self.thread:
                self.thread.join(timeout=15)
                if self.thread.is_alive():
                    raise RuntimeError("owned API thread did not stop")
            if self.sock:
                self.sock.close()
            if self.temp:
                self.temp.cleanup()

    def settings(**kwargs):
        return original_settings(**(kwargs | {"trusted_origins": (origin,)}))

    try:
        _run([str(pg / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
              "--auth=trust", "--encoding=UTF8", "--locale=C"], timeout=120)
        _start_pg_ctl([str(pg / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                       "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"], log)
        started = True
        with patch.object(original, "BootstrapSettings", side_effect=settings), \
             patch.object(original, "TestClient", HttpsClient), \
             patch.object(original, "connect", side_effect=tracked_connect), \
             patch.object(original, "delete_test_credential", side_effect=tracked_delete):
            original.main()
        if len(owned_databases) != 1 or len(deleted_targets) != 1:
            raise ValueError("owned synthetic database/Vault target count mismatch")
        with actual_connect("postgres") as admin:
            for name in owned_databases:
                if admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (name,)).fetchone()[0]:
                    raise ValueError("owned synthetic database remains")
                if admin.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (name,)).fetchone()[0]:
                    raise ValueError("owned synthetic role remains")
        library = ctypes.WinDLL("Advapi32", use_last_error=True)
        library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                                     ctypes.POINTER(ctypes.c_void_p)]
        library.CredReadW.restype = ctypes.c_int
        library.CredFree.argtypes = [ctypes.c_void_p]
        for target in deleted_targets:
            pointer = ctypes.c_void_p()
            found = library.CredReadW(target, 1, 0, ctypes.byref(pointer))
            if found:
                library.CredFree(pointer)
            if found or ctypes.get_last_error() != 1168:
                raise ValueError("owned synthetic Vault target remains or absence unproven")
        if (network_counts["get"] < 7 or network_counts["post"] < 12
                or network_counts["login_secure_cookie"] < 2
                or network_counts["wrong_host_421"] != 2
                or network_counts["wrong_host_api_421"] != 2
                or network_counts["wrong_origin_403"] < 1
                or network_counts["missing_csrf_403"] < 2):
            raise ValueError("real HTTPS login acceptance coverage incomplete")
        return {"status": "SYNTHETIC_CADDY_PRODUCTION_LOGIN_HTTPS_PASS",
                "release_eligible": False, "payload_file_count": count,
                "network_counts": network_counts, "postgresql_ephemeral": True,
                "vault_target_unique_and_absence_verified": True,
                "owned_db_and_role_absence_verified": True,
                "synthetic_tls_only": True, "sse_verified": False}
    finally:
        if started:
            _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], timeout=60)
        if run.resolve().parent == Path(tempfile.gettempdir()).resolve() and run.name.startswith("plm-caddy-login-pg-"):
            status = subprocess.run([str(pg / "pg_ctl.exe"), "-D", str(data), "status"],
                                    capture_output=True, timeout=15, check=False)
            if status.returncode == 0:
                raise RuntimeError(f"owned synthetic PG still running: {run}")
            shutil.rmtree(run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--caddy-inputs", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.layout, args.candidate, args.caddy_inputs), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
