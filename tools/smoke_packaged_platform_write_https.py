"""Exercise packaged --platform-write behind packaged Caddy with synthetic trust.

All mutable resources are disposable Windows-11-only test fixtures. The fixed
candidate is never changed, and no synthetic private key enters the package.
"""

from __future__ import annotations

import base64
import ctypes
import hmac
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import psycopg
from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from sqlalchemy.engine import URL

from install_windows_caddy_go_atomic_rehearsal import rehearse
from preflight_packaged_production_startup_windows import PUBLIC_KEY_RELATIVE
from smoke_caddy_go_layout_https import verify_layout
from smoke_caddy_same_origin_https import caddyfile, synthetic_certificate
from smoke_packaged_pg18_migration import _port, _run
from smoke_windows_pg18_sidecar import _start_pg_ctl
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.license.application.license_validation import PRODUCT_CODE
from plm_assistant.modules.license.infrastructure.packaged_product_key import PRODUCT_KEY_REF
from plm_assistant.modules.license.infrastructure.windows_selected_machine import windows_local_macs
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    DEFAULT_TARGET, read_database_url, write_database_url,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


KEY_REFS = (
    "trusted-time-v1", "user-list-cursor-v1", "secret-list-cursor-v1",
    "project-member-list-cursor-v1", "project-department-list-cursor-v1",
    "audit-list-cursor-v1", "job-list-cursor-v1", "document-list-cursor-v1",
    "document-version-cursor-v1", "document-parse-cursor-v1",
    "document-upload-token-v1", "secret-master-v1",
)


def credential_exists(target: str) -> bool:
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.POINTER(ctypes.c_void_p)]
    library.CredReadW.restype = wintypes.BOOL
    library.CredFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p()
    found = bool(library.CredReadW(target, 1, 0, ctypes.byref(pointer)))
    if found:
        library.CredFree(pointer)
        return True
    if ctypes.get_last_error() != 1168:
        raise ValueError("current-account credential inventory unavailable")
    return False


def _delete_credential(target: str) -> None:
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    library.CredDeleteW.restype = wintypes.BOOL
    if not library.CredDeleteW(target, 1, 0):
        raise ValueError("owned synthetic credential cleanup failed")


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT)
        process.wait(timeout=12)
    except (OSError, subprocess.TimeoutExpired):
        process.terminate()
        process.wait(timeout=12)


def _wait_http(client: httpx.Client, path: str, process: subprocess.Popen, *, seconds: int = 30) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("packaged production child exited before ready")
        try:
            response = client.get(path)
            if response.status_code == 200:
                return
        except (httpx.ConnectError, httpx.ReadError):
            pass
        time.sleep(.1)
    raise ValueError("packaged production child did not become ready")


def smoke(candidate: Path, source: Path, stage: Path, pristine: Path, target: Path) -> dict:
    if sys.platform != "win32" or Path(r"C:\PLMTool").exists():
        raise ValueError("Windows isolated smoke only")
    verified = verify_layout(candidate, source, stage, pristine)
    targets = [DEFAULT_TARGET, *("PLMProjectTool/SecretKey/" + ref for ref in KEY_REFS)]
    if any(credential_exists(name) for name in targets):
        raise ValueError("a fixed current-account product Vault target already exists")
    placed = rehearse(candidate, source, stage, target)
    if verify_layout(candidate, source, stage, target) != verified:
        raise ValueError("fresh synthetic layout differs before trust injection")
    target = target.resolve(strict=True)
    public_file = target / PUBLIC_KEY_RELATIVE
    public_file.parent.mkdir(exist_ok=True)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw,
                                                 serialization.PublicFormat.Raw)
    public_file.write_text(json.dumps({
        "schema_version": "plm.product-public-key.v1", "product_code": PRODUCT_CODE,
        "key_ref": PRODUCT_KEY_REF, "public_key": base64.b64encode(public).decode("ascii"),
    }, sort_keys=True), encoding="ascii")
    del private
    (target / "SYNTHETIC-TRUST-NOT-FOR-RELEASE.txt").write_text(
        "Synthetic public trust fixture only; this layout is not the fixed release candidate.\n",
        encoding="ascii")
    run = Path(tempfile.mkdtemp(prefix="plm-p42-platform-write-", dir=tempfile.gettempdir()))
    pg, runtime, caddy = (target / "runtime/pgsql/bin", target / "runtime/python/python.exe",
                          target / "runtime/caddy/caddy.exe")
    pg_port, api_port, https_port = _port(), _port(), _port()
    while len({pg_port, api_port, https_port}) != 3:
        pg_port, api_port, https_port = _port(), _port(), _port()
    data, log = run / "pgdata", run / "postgresql.log"
    api_process = caddy_process = None
    pg_started = False
    installed_keys: dict[str, bytes] = {}
    db_url: str | None = None
    outcome: dict | None = None
    provider = WindowsSecretKeyProvider()
    try:
        _run([str(pg / "initdb.exe"), f"--pgdata={data}", "--username=poc_admin",
              "--auth=trust", "--encoding=UTF8", "--locale=C"], timeout=120)
        _start_pg_ctl([str(pg / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                       "-o", f"-h 127.0.0.1 -p {pg_port}", "-w", "start"], log)
        pg_started = True
        suffix = uuid.uuid4().hex[:12]
        role, database = f"p42_{suffix}", f"p42_{suffix}"
        password = uuid.uuid4().hex + uuid.uuid4().hex
        with psycopg.connect(host="127.0.0.1", port=pg_port, user="poc_admin",
                            dbname="postgres", autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)))
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(database), sql.Identifier(role)))
        db_url = URL.create("postgresql+psycopg", username=role, password=password,
                            host="127.0.0.1", port=pg_port,
                            database=database).render_as_string(hide_password=False)
        with psycopg.connect(host="127.0.0.1", port=pg_port, user="poc_admin",
                            dbname=database, autocommit=True) as db:
            db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        command.upgrade(create_migration_config(db_url), "head")
        clear = bytearray(b"synthetic-packaged-login-password")
        view = memoryview(clear)
        try:
            hashed = ScryptPasswordHasher().hash_password(view)
        finally:
            view.release()
            clear[:] = b"\x00" * len(clear)
        with psycopg.connect(host="127.0.0.1", port=pg_port, user=role,
                            dbname=database, autocommit=True) as db:
            user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                              "VALUES ('Synthetic Packaged User','synthetic packaged user') RETURNING user_id").fetchone()[0]
            credential = db.execute(
                "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
                "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
                (user, hashed.password_hash, hashed.algorithm_id,
                 '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
            db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
                       "state='ENABLED' WHERE user_id=%s", (credential, user))
        for ref in KEY_REFS:
            if credential_exists("PLMProjectTool/SecretKey/" + ref):
                raise ValueError("product Vault target appeared during synthetic setup")
            value = os.urandom(32)
            installed_keys[ref] = value  # Track even if an API write succeeds then reports an error.
            provider.install_new(ref, value)
        if credential_exists(DEFAULT_TARGET):
            raise ValueError("database Vault target appeared during synthetic setup")
        write_database_url(db_url)
        api_data = run / "api-data"
        api_data.mkdir()
        cert, key, caddy_config = run / "cert.pem", run / "key.pem", run / "Caddyfile"
        synthetic_certificate(cert, key)
        origin = f"https://localhost:{https_port}"
        bootstrap = run / "bootstrap.yaml"
        bootstrap.write_text(
            f'bind_host: "127.0.0.1"\nbind_port: {api_port}\n'
            f'data_root: "{api_data.as_posix()}"\nlog_level: "ERROR"\n'
            f'trusted_origins: ["{origin}"]\n'
            f'selected_mac: "{sorted(windows_local_macs())[0]}"\n', encoding="ascii")
        env = {name: value for name, value in os.environ.items() if not name.upper().startswith("PLM_")}
        env.pop("PYTHONPATH", None)
        env["PATH"] = os.pathsep.join((str(target / "runtime/python"), str(pg),
                                       str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
        api_process = subprocess.Popen(
            [str(runtime), "-I", "-B", "-m", "plm_assistant.entrypoints.serve_windows",
             str(bootstrap), "--platform-write"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        with httpx.Client(base_url=f"http://127.0.0.1:{api_port}", timeout=3,
                          trust_env=False) as direct:
            _wait_http(direct, "/health/ready", api_process)
        caddy_config.write_text(caddyfile(target / "app/frontend/dist", cert, key,
                                          api_port, https_port), encoding="ascii")
        checked = subprocess.run([str(caddy), "validate", "--config", str(caddy_config)],
                                 capture_output=True, text=True, errors="replace", env=env,
                                 timeout=20, check=False)
        if checked.returncode:
            raise ValueError("packaged Caddy synthetic configuration rejected")
        caddy_process = subprocess.Popen([str(caddy), "run", "--config", str(caddy_config)],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, env=env,
                                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        with httpx.Client(base_url=origin, verify=str(cert), timeout=5,
                          follow_redirects=False, trust_env=False) as client:
            _wait_http(client, "/health/ready", caddy_process)
            if client.get("/", headers={"Host": "wrong.example.test"}).status_code != 421:
                raise ValueError("wrong Host not rejected by packaged Caddy")
            body = {"username": "Synthetic Packaged User",
                    "password": "synthetic-packaged-login-password"}
            if client.post("/api/v1/auth/login", json=body,
                           headers={"origin": "https://wrong.example.test"}).status_code != 403:
                raise ValueError("wrong Origin not rejected")
            login = client.post("/api/v1/auth/login", json=body, headers={"origin": origin})
            if (login.status_code != 200 or not all(token in login.headers.get("set-cookie", "")
                    for token in ("Secure", "HttpOnly", "SameSite=lax"))):
                raise ValueError("packaged production login or cookie rejected")
            session = client.get("/api/v1/auth/session")
            if session.status_code != 200:
                raise ValueError("packaged production session read rejected")
            project = client.get("/api/v1/projects")
            if project.status_code == 404 or project.status_code < 400:
                raise ValueError("unlicensed protected Project route not closed")
        outcome = {"status": "SYNTHETIC_PACKAGED_PLATFORM_WRITE_HTTPS_PASS",
                "release_eligible": False, "fixed_candidate_unmodified": True,
                "synthetic_layout_file_count_before_injection": verified["file_count"],
                "packaged_python_process_started": True, "packaged_caddy_started": True,
                "temporary_pg18_started": True, "login_status": 200,
                "session_status": 200, "unlicensed_project_status": project.status_code,
                "synthetic_public_key_only": True, "vault_key_count": len(installed_keys),
                "formal_trust_provisioned": False}
    finally:
        cleanup_errors = []
        for name, process in (("caddy", caddy_process), ("api", api_process)):
            try:
                _stop_process(process)
            except (OSError, subprocess.TimeoutExpired):
                cleanup_errors.append(name)
        pg_stopped = not pg_started
        if pg_started:
            try:
                _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"], timeout=60)
                pg_stopped = True
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                cleanup_errors.append("postgres")
        for ref, expected in installed_keys.items():
            try:
                actual = provider.resolve_key(ref)
                if actual is None:
                    continue
                if not hmac.compare_digest(actual, expected):
                    cleanup_errors.append("vault-ownership")
                    continue
                _delete_credential("PLMProjectTool/SecretKey/" + ref)
            except (OSError, ValueError):
                cleanup_errors.append("vault-key")
        try:
            if db_url is not None and credential_exists(DEFAULT_TARGET):
                if hmac.compare_digest(read_database_url().encode(), db_url.encode()):
                    _delete_credential(DEFAULT_TARGET)
                else:
                    cleanup_errors.append("database-vault-ownership")
            if any(credential_exists(name) for name in targets):
                cleanup_errors.append("vault-remains")
        except (OSError, ValueError):
            cleanup_errors.append("vault-inventory")
        if (run.parent.resolve(strict=True) != Path(tempfile.gettempdir()).resolve(strict=True)
                or not run.name.startswith("plm-p42-platform-write-")
                or target.parent != run.parent or not target.name.startswith("plm-install-rehearsal-")):
            cleanup_errors.append("scope")
        elif pg_stopped and all(process is None or process.poll() is not None
                                  for process in (api_process, caddy_process)):
            try:
                shutil.rmtree(run)
                shutil.rmtree(target)
            except OSError:
                cleanup_errors.append("temporary-files")
        else:
            cleanup_errors.append("process-still-live")
        if cleanup_errors:
            raise ValueError("synthetic cleanup incomplete: " + ",".join(sorted(set(cleanup_errors))))
    if outcome is None:
        raise ValueError("packaged platform smoke did not complete")
    return {**outcome, "temporary_processes_stopped": True,
            "synthetic_vault_targets_absent": True, "temporary_files_removed": True}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "source", "stage", "pristine", "target"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.source, args.stage, args.pristine,
                           args.target), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
