"""Owned, bounded interactive browser fixture; never production credentials."""
import ctypes
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import redirect_stdout
from io import StringIO
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location("_browser_owned_source", ROOT / "validation/aut-03-a07-p03-production-login/verify.py")
source = module_from_spec(spec)
spec.loader.exec_module(source)


def main():
    suffix = uuid.uuid4().hex[:12]
    dbname = role = "aut05a05_" + suffix
    target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    secret = uuid.uuid4().hex + uuid.uuid4().hex
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        proxy_port = reserve.getsockname()[1]
    origin = f"http://127.0.0.1:{proxy_port}"
    proxy = server = thread = sock = None
    logs = StringIO()
    with source.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(secret)))
        try:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(dbname), sql.Identifier(role)))
            try:
                url = URL.create("postgresql+psycopg", username=role, password=secret,
                    host=source.HOST, port=source.PORT, database=dbname)
                with source.connect(dbname) as db:
                    db.execute("CREATE EXTENSION IF NOT EXISTS vector")
                command.upgrade(source.create_migration_config(url), "head")
                clear = bytearray(b"synthetic-browser-password")
                try:
                    with memoryview(clear) as view:
                        hashed = source.ScryptPasswordHasher().hash_password(view)
                finally:
                    clear[:] = b"\x00" * len(clear)
                with source.connect(dbname) as db:
                    user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                        "VALUES ('Synthetic Browser User','synthetic browser user') RETURNING user_id").fetchone()[0]
                    credential = db.execute("INSERT INTO plm.auth_password_credentials "
                        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,%s,%s,%s::jsonb) "
                        "RETURNING password_credential_id", (user, hashed.password_hash, hashed.algorithm_id,
                        '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
                    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' "
                        "WHERE user_id=%s", (credential, user))
                source.write_database_url(url.render_as_string(hide_password=False), target=target)
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        settings = source.BootstrapSettings(data_root=Path(directory), trusted_origins=(origin,))
                        with redirect_stdout(logs):
                            app = source.create_production_login_app(settings, credential_target=target)
                        sock = socket.socket()
                        sock.bind(("127.0.0.1", 0)); sock.listen(128)
                        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
                        thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=False)
                        thread.start()
                        deadline = monotonic() + 15
                        while not server.started:
                            if not thread.is_alive() or monotonic() > deadline: raise RuntimeError("Owned backend startup failed")
                            sleep(.05)
                        proxy = subprocess.Popen(["node", str(ROOT / "validation/aut-05-a04-network-login/start-proxy.mjs"),
                            str(proxy_port), str(sock.getsockname()[1])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        ready = queue.Queue()
                        Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
                        if ready.get(timeout=15) != "OWNED_PROXY_READY": raise RuntimeError("Owned proxy startup failed")
                        print("BROWSER_FIXTURE_READY " + origin + "/login", flush=True)
                        actions = queue.Queue()
                        Thread(target=lambda: actions.put(sys.stdin.readline().strip()), daemon=True).start()
                        assert actions.get(timeout=900) == "VERIFY", "Browser verification not completed"
                        with source.connect(dbname) as db:
                            assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 4
                            for action, expected in (("SESSION_ISSUED", 3), ("SESSION_RENEWED", 1), ("SESSION_REVOKED", 2)):
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action=%s", (action,)).fetchone()[0] == expected
                            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AUTH_LOGOUT'").fetchone()[0] == 2
                        print("BROWSER_DATABASE_COUNTS PASS: 4 sessions/3 issued/1 renewed/2 revoked/2 receipts", flush=True)
                finally:
                    if proxy:
                        if proxy.poll() is None:
                            try:
                                proxy.stdin.write("STOP\n"); proxy.stdin.flush(); proxy.wait(timeout=10)
                            except (BrokenPipeError, subprocess.TimeoutExpired):
                                proxy.kill(); proxy.wait(timeout=10)
                        proxy.stdin.close(); proxy.stdout.close()
                    if server: server.should_exit = True
                    if thread:
                        thread.join(timeout=10)
                        assert not thread.is_alive(), "Owned backend did not stop"
                    if sock: sock.close()
                    source.delete_test_credential(target)
            finally:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        finally:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (dbname,)).fetchone()[0] == 0
        assert admin.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0] == 0
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
    library.CredReadW.restype = ctypes.c_int
    pointer = ctypes.c_void_p()
    found = library.CredReadW(target, 1, 0, ctypes.byref(pointer))
    if found:
        library.CredFree.argtypes = [ctypes.c_void_p]; library.CredFree(pointer)
    assert not found and ctypes.get_last_error() == 1168
    print("BROWSER_FIXTURE_CLEANUP PASS: owned services stopped; database/role absent; Vault absence1168", flush=True)


if __name__ == "__main__":
    main()
