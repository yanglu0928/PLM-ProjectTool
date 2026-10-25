"""Exercise packaged --platform-write behind packaged Caddy with synthetic trust.

All mutable resources are disposable Windows-11-only test fixtures. The fixed
candidate is never changed, and no synthetic private key enters the package.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
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


_ACTIVE_API_RESTART: ContextVar[Callable[[], None] | None] = ContextVar(
    "packaged_smoke_api_restart", default=None)
_ACTIVE_POSTGRES_RESTART: ContextVar[Callable[[], None] | None] = ContextVar(
    "packaged_smoke_postgres_restart", default=None)
_ACTIVE_POSTGRES_LOGICAL_RESTORE: ContextVar[Callable[[], dict] | None] = ContextVar(
    "packaged_smoke_postgres_logical_restore", default=None)


def current_packaged_api_restart() -> Callable[[], None]:
    """Return the restart hook only while an owned packaged smoke is active."""
    restart = _ACTIVE_API_RESTART.get()
    if not callable(restart):
        raise RuntimeError("packaged API restart is available only inside its smoke callback")
    return restart


def current_packaged_postgres_restart() -> Callable[[], None]:
    """Return the PostgreSQL restart hook only inside its owned smoke callback."""
    restart = _ACTIVE_POSTGRES_RESTART.get()
    if not callable(restart):
        raise RuntimeError("packaged PostgreSQL restart is available only inside its smoke callback")
    return restart


def current_packaged_postgres_logical_restore() -> Callable[[], dict]:
    """Return a restore hook limited to this smoke's disposable PG cluster."""
    restore = _ACTIVE_POSTGRES_LOGICAL_RESTORE.get()
    if not callable(restore):
        raise RuntimeError("packaged PostgreSQL restore is available only inside its smoke callback")
    return restore


KEY_REFS = (
    "trusted-time-v1", "user-list-cursor-v1", "secret-list-cursor-v1",
    "project-member-list-cursor-v1", "project-department-list-cursor-v1",
    "audit-list-cursor-v1", "job-list-cursor-v1", "document-list-cursor-v1",
    "document-version-cursor-v1", "document-parse-cursor-v1",
    "document-upload-token-v1", "secret-master-v1",
    "ai-model-list-cursor-v1", "ai-prompt-list-cursor-v1",
    "ai-provider-list-cursor-v1", "ai-read-cursor-v1",
    "evidence-list-cursor-v1", "global-reference-list-cursor-v1",
    "project-global-reference-candidate-list-cursor-v1",
    "project-outline-list-cursor-v1", "project-outline-version-list-cursor-v1",
    "project-plan-list-cursor-v1", "project-reference-list-cursor-v1",
    "project-section-list-cursor-v1", "project-section-version-list-cursor-v1",
    "project-structured-spec-version-list-cursor-v1",
    "prototype-list-cursor-v1", "prototype-package-cursor-v1",
    "prototype-requirement-link-cursor-v1", "prototype-template-cursor-v1",
    "prototype-version-cursor-v1", "review-list-cursor-v1",
    "trace-graph-cursor-v1",
    "capability-baseline-cursor-v1", "capability-child-cursor-v1",
    "handover-action-cursor-v1", "handover-analysis-cursor-v1",
    "handover-item-cursor-v1", "handover-version-cursor-v1",
    "requirement-cursor-v1", "requirement-package-cursor-v1",
    "requirement-relation-cursor-v1", "requirement-version-cursor-v1",
    "survey-assignment-cursor-v1", "survey-conclusion-cursor-v1",
    "survey-cursor-v1", "survey-round-cursor-v1", "survey-version-cursor-v1",
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
            diagnostic = "stderr unavailable"
            if process.stderr is not None:
                raw = process.stderr.read(65536)
                lines = raw.decode("utf-8", errors="replace").splitlines()
                for line in reversed(lines):
                    match = re.match(r"([\w.]+(?:Error|Exception))(?::\s*(.*))?", line)
                    if match:
                        kind, message = match.groups()
                        missing = re.fullmatch(r"No module named '([\w.]+)'", message or "")
                        diagnostic = (f"{kind}: missing module {missing.group(1)}"
                                      if missing else kind)
                        break
                else:
                    diagnostic = "stderr-sha256:" + hashlib.sha256(raw).hexdigest()[:12]
            raise ValueError("packaged production child exited before ready: " + diagnostic)
        try:
            response = client.get(path)
            if response.status_code == 200:
                return
        except (httpx.ConnectError, httpx.ReadError):
            pass
        time.sleep(.1)
    raise ValueError("packaged production child did not become ready")


def _diagnose_packaged_factory(runtime: Path, bootstrap: Path,
                               env: dict[str, str]) -> str:
    """Return only exception class and source location; never print config/credentials."""
    code = (
        "import sys,traceback; from pathlib import Path; "
        "from plm_assistant.modules.platform.infrastructure.bootstrap_config "
        "import load_bootstrap_settings; "
        "from plm_assistant.entrypoints.production_login "
        "import create_production_platform_write_app; "
        "settings=load_bootstrap_settings(Path(sys.argv[1])); "
        "\ntry: create_production_platform_write_app(settings); print('FACTORY_OK')"
        "\nexcept Exception as error:"
        "\n frame=traceback.extract_tb(error.__traceback__)[-1]; "
        "print(type(error).__name__+'@'+Path(frame.filename).name+':'+str(frame.lineno)); "
        "raise SystemExit(1)"
    )
    result = subprocess.run([str(runtime), "-I", "-B", "-c", code, str(bootstrap)],
                            capture_output=True, text=True, errors="replace", env=env,
                            timeout=30, check=False)
    label = result.stdout.strip().splitlines()[-1:] or ["NO_FACTORY_RESULT"]
    return label[0] if re.fullmatch(r"(?:FACTORY_OK|[\w]+Error@[\w.]+:\d+)", label[0]) else "NO_FACTORY_RESULT"


def smoke(candidate: Path, source: Path, stage: Path, pristine: Path, target: Path, *,
          layout_verifier=None, layout_rehearser=None,
          synthetic_license_document_factory=None, licensed_https_probe=None) -> dict:
    if sys.platform != "win32" or Path(r"C:\PLMTool").exists():
        raise ValueError("Windows isolated smoke only")
    if (synthetic_license_document_factory is None) != (licensed_https_probe is None):
        raise ValueError("synthetic licensed HTTPS callbacks must be paired")
    check_layout = layout_verifier or verify_layout
    place_layout = layout_rehearser or rehearse
    verified = check_layout(candidate, source, stage, pristine)
    targets = [DEFAULT_TARGET, *("PLMProjectTool/SecretKey/" + ref for ref in KEY_REFS)]
    if any(credential_exists(name) for name in targets):
        raise ValueError("a fixed current-account product Vault target already exists")
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw,
                                                 serialization.PublicFormat.Raw)
    selected_mac = sorted(windows_local_macs())[0]
    if synthetic_license_document_factory is not None:
        shape_probe = synthetic_license_document_factory(private, selected_mac)
        if type(shape_probe) is not bytes or not 1 <= len(shape_probe) <= 16384:
            raise ValueError("synthetic signed document rejected")
        del shape_probe
    # The disposable trust document is created only after the package, database,
    # API and HTTPS listener are ready. This keeps short-lived synthetic License
    # validity windows tied to the actual licensed probe, not archive hashing/setup.
    signed_document = None
    if synthetic_license_document_factory is None:
        del private
    place_layout(candidate, source, stage, target)
    if check_layout(candidate, source, stage, target) != verified:
        raise ValueError("fresh synthetic layout differs before trust injection")
    target = target.resolve(strict=True)
    public_file = target / PUBLIC_KEY_RELATIVE
    public_file.parent.mkdir(exist_ok=True)
    public_file.write_text(json.dumps({
        "schema_version": "plm.product-public-key.v1", "product_code": PRODUCT_CODE,
        "key_ref": PRODUCT_KEY_REF, "public_key": base64.b64encode(public).decode("ascii"),
    }, sort_keys=True), encoding="ascii")
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
    pg_restart_count = 0
    pg_logical_restore_count = 0
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

        def restart_postgres() -> None:
            """Restart only this smoke's isolated cluster using the same data and port."""
            nonlocal pg_restart_count
            _run([str(pg / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"],
                 timeout=60)
            # Keep cleanup ownership set even if the subsequent start fails.
            _start_pg_ctl([str(pg / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                           "-o", f"-h 127.0.0.1 -p {pg_port}", "-w", "start"], log)
            with psycopg.connect(host="127.0.0.1", port=pg_port, user="poc_admin",
                                 dbname="postgres", autocommit=True,
                                 connect_timeout=5) as check:
                if check.execute("SELECT 1").fetchone() != (1,):
                    raise ValueError("restarted isolated PostgreSQL readiness query failed")
            pg_restart_count += 1

        def backup_restore_postgres_database() -> dict:
            """Dump and restore only this smoke's database into a fresh sibling DB."""
            nonlocal pg_logical_restore_count
            suffix = uuid.uuid4().hex[:10]
            restored_database = f"{database[:45]}_r_{suffix}"
            backup = run / f"p51-a11-{suffix}.dump"
            if backup.exists() or not run.is_dir():
                raise ValueError("owned PostgreSQL backup path is not fresh")
            pg_env = {name: value for name, value in os.environ.items()
                      if not name.upper().startswith("PG")}
            pg_env["PGPASSWORD"] = password
            target_created = False
            try:
                _run([str(pg / "pg_dump.exe"), "--host=127.0.0.1",
                      f"--port={pg_port}", f"--username={role}",
                      f"--dbname={database}", "--format=custom", "--no-owner",
                      "--no-acl", f"--file={backup}"], env=pg_env, timeout=180)
                if (not backup.is_file() or backup.stat().st_size < 64 or
                        backup.resolve().parent != run.resolve()):
                    raise ValueError("packaged pg_dump did not produce an owned backup")
                with psycopg.connect(host="127.0.0.1", port=pg_port, user="poc_admin",
                                     dbname="postgres", autocommit=True) as admin:
                    admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(restored_database), sql.Identifier(role)))
                target_created = True
                restore_env = {name: value for name, value in os.environ.items()
                               if not name.upper().startswith("PG")}
                restore_env["PGPASSWORD"] = ""
                _run([str(pg / "pg_restore.exe"), "--host=127.0.0.1",
                      f"--port={pg_port}", "--username=poc_admin",
                      f"--dbname={restored_database}", "--exit-on-error",
                      "--schema-only", "--no-owner", "--no-acl", str(backup)],
                     env=restore_env, timeout=240)
                _run([str(pg / "pg_restore.exe"), "--host=127.0.0.1",
                      f"--port={pg_port}", "--username=poc_admin",
                      f"--dbname={restored_database}", "--exit-on-error",
                      "--data-only", "--disable-triggers", "--no-owner",
                      "--no-acl", str(backup)],
                     env=restore_env, timeout=240)
                with psycopg.connect(host="127.0.0.1", port=pg_port, user="poc_admin",
                                     dbname=restored_database, autocommit=True,
                                     connect_timeout=5) as restored:
                    if restored.execute("SELECT 1").fetchone() != (1,):
                        raise ValueError("restored packaged PostgreSQL database is not queryable")
                pg_logical_restore_count += 1
                backup_bytes = backup.stat().st_size
                backup.unlink()

                def drop_restored_database() -> None:
                    with psycopg.connect(host="127.0.0.1", port=pg_port,
                                         user="poc_admin", dbname="postgres",
                                         autocommit=True, connect_timeout=5) as admin:
                        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                            sql.Identifier(restored_database)))

                return {
                    "database": restored_database,
                    "backup_bytes": backup_bytes,
                    "connect_restored_db": lambda: psycopg.connect(
                        host="127.0.0.1", port=pg_port, user="poc_admin",
                        dbname=restored_database, autocommit=True, connect_timeout=5),
                    "drop_restored_db": drop_restored_database,
                    "backup_removed": not backup.exists(),
                }
            except BaseException:
                if target_created:
                    try:
                        with psycopg.connect(host="127.0.0.1", port=pg_port,
                                             user="poc_admin", dbname="postgres",
                                             autocommit=True, connect_timeout=5) as admin:
                            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                                sql.Identifier(restored_database)))
                    except Exception:
                        pass
                raise
            finally:
                if backup.exists():
                    backup.unlink()
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
            f'selected_mac: "{selected_mac}"\n', encoding="ascii")
        env = {name: value for name, value in os.environ.items() if not name.upper().startswith("PLM_")}
        env.pop("PYTHONPATH", None)
        env["PATH"] = os.pathsep.join((str(target / "runtime/python"), str(pg),
                                       str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
        api_command = [str(runtime), "-I", "-B", "-m",
                       "plm_assistant.entrypoints.serve_windows",
                       str(bootstrap), "--platform-write"]

        def start_api() -> subprocess.Popen:
            return subprocess.Popen(
                api_command, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

        api_process = start_api()
        with httpx.Client(base_url=f"http://127.0.0.1:{api_port}", timeout=3,
                          trust_env=False) as direct:
            try:
                _wait_http(direct, "/health/ready", api_process)
            except ValueError as startup_error:
                diagnostic = _diagnose_packaged_factory(runtime, bootstrap, env)
                raise ValueError(f"{startup_error}; packaged factory={diagnostic}") from None

        api_restart_count = 0

        def restart_api() -> None:
            """Restart only this smoke's API process; retain its DB and Caddy."""
            nonlocal api_process, api_restart_count
            previous = api_process
            if previous is None or previous.poll() is not None:
                raise ValueError("owned packaged API is not running")
            _stop_process(previous)
            if previous.poll() is None:
                raise ValueError("owned packaged API did not stop")
            api_process = start_api()
            with httpx.Client(base_url=f"http://127.0.0.1:{api_port}", timeout=3,
                              trust_env=False) as direct:
                _wait_http(direct, "/health/ready", api_process)
            api_restart_count += 1
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
            if licensed_https_probe is not None:
                signed_document = synthetic_license_document_factory(private, selected_mac)
                del private
                if type(signed_document) is not bytes or not 1 <= len(signed_document) <= 16384:
                    raise ValueError("synthetic signed document rejected")
                def connect_db():
                    return psycopg.connect(host="127.0.0.1", port=pg_port, user=role,
                                          password=password, dbname=database, autocommit=True)
                def connect_fixture_db():
                    # Privileged fixture access is confined to this disposable DB;
                    # product/API assertions continue through the least-privileged app role.
                    return psycopg.connect(host="127.0.0.1", port=pg_port, user="poc_admin",
                                           dbname=database, autocommit=True)
                restart_token = _ACTIVE_API_RESTART.set(restart_api)
                postgres_restart_token = _ACTIVE_POSTGRES_RESTART.set(restart_postgres)
                restore_token = _ACTIVE_POSTGRES_LOGICAL_RESTORE.set(
                    backup_restore_postgres_database)
                try:
                    licensed_https_probe(client=client, connect_db=connect_db,
                                         fixture_db=connect_fixture_db,
                                         user_id=user, signed_document=signed_document,
                                         selected_mac=selected_mac, login=login, origin=origin)
                finally:
                    _ACTIVE_POSTGRES_LOGICAL_RESTORE.reset(restore_token)
                    _ACTIVE_POSTGRES_RESTART.reset(postgres_restart_token)
                    _ACTIVE_API_RESTART.reset(restart_token)
        outcome = {"status": "SYNTHETIC_PACKAGED_PLATFORM_WRITE_HTTPS_PASS",
                "release_eligible": False, "fixed_candidate_unmodified": True,
                "synthetic_layout_file_count_before_injection": verified["file_count"],
                "packaged_python_process_started": True, "packaged_caddy_started": True,
                "temporary_pg18_started": True, "login_status": 200,
                "session_status": 200, "unlicensed_project_status": project.status_code,
                "synthetic_public_key_only": True, "vault_key_count": len(installed_keys),
                "formal_trust_provisioned": False,
                "api_restart_count": api_restart_count,
                "postgres_restart_count": pg_restart_count,
                "postgres_logical_restore_count": pg_logical_restore_count}
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
