"""Original real PG/Vault login acceptance, replacing only ASGI transport."""
import queue
import ctypes
import re
from contextlib import redirect_stdout
from io import StringIO
import socket
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from unittest.mock import patch

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location("_network_login_original", ROOT / "validation/aut-03-a07-p03-production-login/verify.py")
original = module_from_spec(spec)
spec.loader.exec_module(original)
settings_type = original.BootstrapSettings


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    proxy_port = free_port()
    origin = f"http://127.0.0.1:{proxy_port}"
    requests = {"GET": 0, "POST": 0}
    utc_expiries = {"/api/v1/auth/login": 0, "/api/v1/auth/session": 0,
                    "/api/v1/auth/session:renew": 0}
    contexts = []
    owned_databases = set()
    deleted_targets = []
    actual_connect = original.connect
    actual_delete = original.delete_test_credential

    def tracked_connect(name):
        if name != "postgres":
            owned_databases.add(name)
        return actual_connect(name)

    def tracked_delete(target):
        actual_delete(target)
        deleted_targets.append(target)

    class NetworkClient:
        def __init__(self, app, **unused):
            self.app = app
            self.server = None
            self.thread = None
            self.proxy = None
            self.client = None
            self.sock = None

        def __enter__(self):
            try:
                self.sock = socket.socket()
                self.sock.bind(("127.0.0.1", 0))
                self.sock.listen(128)
                backend_port = self.sock.getsockname()[1]
                self.server = uvicorn.Server(uvicorn.Config(self.app, log_level="critical", access_log=False,
                    proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
                self.thread = Thread(target=lambda: self.server.run(sockets=[self.sock]), daemon=False)
                self.thread.start()
                deadline = monotonic() + 15
                while not self.server.started:
                    if not self.thread.is_alive() or monotonic() > deadline:
                        raise RuntimeError("Owned backend failed startup")
                    sleep(.05)
                self.proxy = subprocess.Popen(["node", str(Path(__file__).with_name("start-proxy.mjs")),
                    str(proxy_port), str(backend_port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                ready = queue.Queue()
                Thread(target=lambda: ready.put(self.proxy.stdout.readline().strip()), daemon=True).start()
                if ready.get(timeout=15) != "OWNED_PROXY_READY":
                    raise RuntimeError("Owned proxy failed startup")
                self.client = httpx.Client(base_url=origin, timeout=5, follow_redirects=False, trust_env=False)
                contexts.append("REAL_NETWORK_READY")
                return self
            except Exception:
                self.__exit__(None, None, None)
                raise

        def request(self, method, path, **kwargs):
            headers = dict(kwargs.pop("headers", {}))
            for key, value in tuple(headers.items()):
                if key.lower() == "origin" and value == "http://localhost":
                    headers[key] = origin
            response = self.client.request(method, path, headers=headers, **kwargs)
            requests[method] += 1
            assert response.headers.get("access-control-allow-origin") is None
            if response.status_code == 200 and path in utc_expiries:
                data = response.json()["data"]
                for field in ("absolute_expires_at", "idle_expires_at"):
                    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", data[field]), (
                        "Auth Session response must use the frozen UTC wire format")
                utc_expiries[path] += 1
            return response

        def get(self, path, **kwargs):
            return self.request("GET", path, **kwargs)

        def post(self, path, **kwargs):
            return self.request("POST", path, **kwargs)

        def __exit__(self, *args):
            if self.client:
                self.client.close()
            if self.proxy:
                try:
                    if self.proxy.poll() is None:
                        self.proxy.stdin.write("STOP\n")
                        self.proxy.stdin.flush()
                        self.proxy.wait(timeout=10)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    self.proxy.kill()
                    self.proxy.wait(timeout=10)
                finally:
                    for stream in (self.proxy.stdin, self.proxy.stdout):
                        stream.close()
            if self.server:
                self.server.should_exit = True
            if self.thread:
                self.thread.join(timeout=10)
                if self.thread.is_alive():
                    raise RuntimeError("Owned backend not stopped; verification failed")
            if self.sock:
                self.sock.close()

    def configured_settings(**kwargs):
        return settings_type(**(kwargs | {"trusted_origins": (origin,)}))

    # Original application logging is retained, but diagnostics are not printed
    # or persisted by this validation process; no production logger is disabled.
    with redirect_stdout(StringIO()):
        with patch.object(original, "BootstrapSettings", side_effect=configured_settings), \
            patch.object(original, "TestClient", NetworkClient), \
            patch.object(original, "connect", side_effect=tracked_connect), \
            patch.object(original, "delete_test_credential", side_effect=tracked_delete):
            original.main()
    assert len(contexts) == 2 and requests["POST"] >= 12 and requests["GET"] >= 7
    assert all(count > 0 for count in utc_expiries.values()), "All three Auth responses must be exercised"
    assert len(owned_databases) == len(deleted_targets) == 1
    with actual_connect("postgres") as admin:
        for name in owned_databases:
            assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (name,)).fetchone()[0] == 0
            assert admin.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (name,)).fetchone()[0] == 0
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
    library.CredReadW.restype = ctypes.c_int
    library.CredFree.argtypes = [ctypes.c_void_p]
    for target in deleted_targets:
        pointer = ctypes.c_void_p()
        found = library.CredReadW(target, 1, 0, ctypes.byref(pointer))
        if found:
            library.CredFree(pointer)
        assert not found and ctypes.get_last_error() == 1168, "Owned Vault target still exists or absence not verified"
    print(f"NETWORK_LOGIN PASS: two real Uvicorn/Vite contexts, {requests['GET']} GET/{requests['POST']} POST; "
        "three Auth expiry projections UTC-Z; original PG/Vault/Cookie/CSRF/replay/concurrent/Audit assertions; "
        "owned sources cleaned; not browser/TLS/production trust")


if __name__ == "__main__":
    main()
