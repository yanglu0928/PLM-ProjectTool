"""Owned Windows browser/PG fixture for read-only Project UI verification."""

from __future__ import annotations

import ctypes
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch

import uvicorn
import httpx
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints import production_login as production
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer


ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location("_owned_source", ROOT / "validation/aut-03-a07-p03-production-login/verify.py")
source = module_from_spec(spec)
spec.loader.exec_module(source)


class SyntheticGuard:
    def require_valid(self, *, trace_id):
        assert isinstance(trace_id, uuid.UUID)
        return object()


def reserve_port():
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def insert_user(db, name: str, password_hash, algorithm_id: str):
    user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                      "VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials "
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
        (user, password_hash, algorithm_id, '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' "
               "WHERE user_id=%s", (credential, user))
    return user


def verify_http(origin: str, owned: uuid.UUID, foreign: uuid.UUID):
    with httpx.Client(base_url=origin, timeout=20) as member:
        assert member.get("/api/v1/projects").status_code == 401
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        listing = member.get("/api/v1/projects")
        assert listing.status_code == 200, listing.text
        data = listing.json()["data"]
        assert data["next_cursor"] is None and data["has_more"] is False
        assert len(data["items"]) == 1 and data["items"][0]["project_id"] == str(owned)
        detail = member.get(f"/api/v1/projects/{owned}")
        assert detail.status_code == 200 and detail.headers["ETag"] == detail.json()["data"]["etag"]
        assert detail.json()["data"]["project_id"] == str(owned)
        rejected = member.get(f"/api/v1/projects/{foreign}")
        assert rejected.status_code == 404 and rejected.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert "Synthetic Foreign Project" not in rejected.text
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200 and login.json()["data"]["deployment_role"] == "DEPLOYMENT_ADMIN"
        listing = admin.get("/api/v1/projects")
        assert listing.status_code == 200 and listing.json()["data"]["items"] == []
        rejected = admin.get(f"/api/v1/projects/{owned}")
        assert rejected.status_code == 404 and rejected.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    print("PROJECT_BROWSER_HTTP PASS: no Cookie401, member list/detail200, foreign404, admin empty/404", flush=True)


def verify_create_http(origin: str, manager: uuid.UUID) -> uuid.UUID:
    body = {"code": "CREATE-P04", "name": "Synthetic Created Project",
            "initial_manager_user_id": str(manager)}
    key = "synthetic-project-create-p04"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        denied = anonymous.post("/api/v1/projects", headers={"Origin": origin,
            "X-CSRF-Token": "a" * 64, "Idempotency-Key": key}, json=body)
        assert denied.status_code == 401, denied.text
    with httpx.Client(base_url=origin, timeout=20) as member:
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        denied = member.post("/api/v1/projects", headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"], "Idempotency-Key": key}, json=body)
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200 and login.json()["data"]["deployment_role"] == "DEPLOYMENT_ADMIN"
        users = admin.get("/api/v1/admin/users", params={"page_size": 50})
        assert users.status_code == 200, users.text
        candidate = next((item for item in users.json()["data"]["items"]
                          if item["user_id"] == str(manager)), None)
        assert candidate is not None and candidate["account_state"] == "ENABLED"
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["data"]["csrf_token"],
                   "Idempotency-Key": key}
        first = admin.post("/api/v1/projects", headers=headers, json=body)
        replay = admin.post("/api/v1/projects", headers=headers, json=body)
        assert first.status_code == replay.status_code == 201, (first.text, replay.text)
        assert first.json()["data"] == replay.json()["data"]
        created = uuid.UUID(first.json()["data"]["project_id"])
        assert first.headers["ETag"] == '"v0"'
        assert first.headers["Location"] == f"/api/v1/projects/{created}"
        conflicting = admin.post("/api/v1/projects", headers=headers,
                                 json={**body, "name": "Changed"})
        assert conflicting.status_code == 409 and conflicting.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY"
        print("PROJECT_CREATE_HTTP PASS: anonymous401, member404, admin candidates200/create201/replay201/conflict409", flush=True)
        return created


def verify_member_http(origin: str, owned: uuid.UUID, foreign: uuid.UUID):
    with httpx.Client(base_url=origin, timeout=20) as viewer:
        login = viewer.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Viewer", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        assert viewer.get(f"/api/v1/projects/{owned}").status_code == 200
        denied = viewer.get(f"/api/v1/projects/{owned}/members?page_size=50")
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        assert admin.get(f"/api/v1/projects/{owned}/members?page_size=50").status_code == 404
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        first = manager.get(f"/api/v1/projects/{owned}/members?page_size=50")
        assert first.status_code == 200, first.text
        page = first.json()["data"]
        assert len(page["items"]) == 50 and page["has_more"] is True and page["next_cursor"]
        second = manager.get(f"/api/v1/projects/{owned}/members", params={"page_size": 50, "cursor": page["next_cursor"]})
        assert second.status_code == 200, second.text
        tail = second.json()["data"]
        assert len(tail["items"]) == 2 and tail["has_more"] is False and tail["next_cursor"] is None
        items = page["items"] + tail["items"]
        assert len({item["member_id"] for item in items}) == 52
        assert sum(item["state"] == "REMOVED" for item in items) == 1
        assert not any("password_hash" in str(item) for item in items)
        assert manager.get(f"/api/v1/projects/{foreign}/members?page_size=50").status_code == 404
        wrong_size = manager.get(f"/api/v1/projects/{owned}/members",
            params={"page_size": 20, "cursor": page["next_cursor"]})
        assert wrong_size.status_code == 400, wrong_size.text
    print("PROJECT_MEMBER_BROWSER_HTTP PASS: viewer/admin404, manager50+2, removed history, foreign404, cursor binding400", flush=True)


def main():
    suffix = uuid.uuid4().hex[:12]
    dbname = role = "prj05a04_" + suffix
    target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    role_secret = uuid.uuid4().hex + uuid.uuid4().hex
    port = reserve_port()
    origin = f"http://127.0.0.1:{port}"
    proxy = server = thread = sock = None
    logs = StringIO()
    with source.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(role_secret)))
        try:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(dbname), sql.Identifier(role)))
            try:
                url = URL.create("postgresql+psycopg", username=role, password=role_secret,
                                 host=source.HOST, port=source.PORT, database=dbname)
                with source.connect(dbname) as db:
                    db.execute("CREATE EXTENSION IF NOT EXISTS vector")
                command.upgrade(source.create_migration_config(url), "head")
                clear = bytearray(b"synthetic-project-only-password")
                try:
                    with memoryview(clear) as view:
                        hashed = source.ScryptPasswordHasher().hash_password(view)
                finally:
                    clear[:] = b"\x00" * len(clear)
                with source.connect(dbname) as db:
                    member = insert_user(db, "Synthetic Project Member", hashed.password_hash, hashed.algorithm_id)
                    admin_user = insert_user(db, "Synthetic Project Admin", hashed.password_hash, hashed.algorithm_id)
                    create_mode = "--create-api-only" in sys.argv[1:] or "--create-browser" in sys.argv[1:]
                    state_mode = "--user-state-browser" in sys.argv[1:]
                    name_mode = "--user-name-browser" in sys.argv[1:]
                    member_mode = ("--member-browser" in sys.argv[1:]
                                   or "--member-api-only" in sys.argv[1:])
                    if sum((create_mode, state_mode, name_mode, member_mode)) > 1:
                        raise ValueError("Browser write modes must be exclusive")
                    manager = (insert_user(db, "Synthetic First Manager", hashed.password_hash, hashed.algorithm_id)
                               if create_mode else None)
                    db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s", (admin_user,))
                    project = db.execute("INSERT INTO plm.prj_projects "
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('OWNED','owned','Synthetic Owned Project',%s) RETURNING project_id", (member,)).fetchone()[0]
                    foreign = db.execute("INSERT INTO plm.prj_projects "
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('FOREIGN','foreign','Synthetic Foreign Project',%s) RETURNING project_id", (admin_user,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments "
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'D1','d1','Synthetic Department') RETURNING department_id", (project,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members "
                        "(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, member, department))
                    if member_mode:
                        viewer = insert_user(db, "Synthetic Project Viewer", hashed.password_hash, hashed.algorithm_id)
                        db.execute("INSERT INTO plm.prj_project_members "
                            "(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')", (project, viewer, department))
                        for index in range(50):
                            history_user = insert_user(db, f"Synthetic History {index:02d}",
                                                       hashed.password_hash, hashed.algorithm_id)
                            historical = db.execute("INSERT INTO plm.prj_project_members "
                                "(project_id,user_id,department_id,project_role) "
                                "VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id",
                                (project, history_user, department)).fetchone()[0]
                            if index == 49:
                                db.execute("UPDATE plm.prj_project_members SET state='REMOVED', "
                                    "ended_at=clock_timestamp(), lock_version=1 WHERE project_member_id=%s",
                                    (historical,))
                source.write_database_url(url.render_as_string(hide_password=False), target=target)
                try:
                    with tempfile.TemporaryDirectory(prefix="plm-project-browser-") as directory, ExitStack() as stack:
                        settings = BootstrapSettings(data_root=Path(directory), trusted_origins=(origin,))
                        prefix = "plm_assistant.entrypoints.production_login."
                        stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                                                  return_value=SimpleNamespace(guard=SyntheticGuard())))
                        for name, codec in (
                            ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                            ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                            ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                            ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                            ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                            ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                            ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                            ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                            ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                        ):
                            stack.enter_context(patch(prefix + name, return_value=codec))
                        if state_mode or name_mode:
                            stack.enter_context(patch(
                                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                                return_value=object()))
                            stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                                return_value=HmacUploadTokenIssuer(
                                    provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                                    key_ref="synthetic-browser-upload-token")))
                        with redirect_stdout(logs):
                            factory = (production.create_production_platform_write_app if state_mode or name_mode
                                       else production.create_production_platform_app)
                            app = factory(settings, credential_target=target)
                        sock = socket.socket()
                        sock.bind(("127.0.0.1", 0))
                        sock.listen(128)
                        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
                        thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=False)
                        thread.start()
                        deadline = monotonic() + 15
                        while not server.started:
                            if not thread.is_alive() or monotonic() > deadline:
                                raise RuntimeError("Owned backend startup failed")
                            sleep(.05)
                        proxy = subprocess.Popen(["node", str(ROOT / "validation/aut-05-a04-network-login/start-proxy.mjs"),
                            str(port), str(sock.getsockname()[1])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        ready = queue.Queue()
                        Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
                        if ready.get(timeout=15) != "OWNED_PROXY_READY":
                            raise RuntimeError("Owned proxy startup failed")
                        print(f"PROJECT_BROWSER_READY {origin}/login OWNED={project} FOREIGN={foreign}"
                              + (f" MANAGER={manager}" if create_mode else "")
                              + (f" USER_STATE_TARGET={member}" if state_mode else "")
                              + (f" USER_NAME_TARGET={member}" if name_mode else ""), flush=True)
                        if "--create-api-only" in sys.argv[1:]:
                            assert manager is not None
                            created = verify_create_http(origin, manager)
                        elif "--api-only" in sys.argv[1:]:
                            verify_http(origin, project, foreign)
                        elif "--member-api-only" in sys.argv[1:]:
                            verify_member_http(origin, project, foreign)
                        else:
                            actions = queue.Queue()
                            Thread(target=lambda: actions.put(sys.stdin.readline().strip()), daemon=True).start()
                            assert actions.get(timeout=900) == "VERIFY", "Browser verification not completed"
                        with source.connect(dbname) as db:
                            expected = 3 if create_mode else 2
                            assert db.execute("SELECT count(*) FROM plm.prj_projects").fetchone()[0] == expected
                            session_count = db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0]
                            if "--api-only" in sys.argv[1:] or "--create-api-only" in sys.argv[1:]:
                                assert session_count == 2
                            elif "--member-api-only" in sys.argv[1:]:
                                assert session_count == 3
                            else:
                                assert session_count >= (1 if create_mode else 2)
                            active_expected = 51 if member_mode else (2 if expected == 3 else 1)
                            assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE state='ACTIVE'").fetchone()[0] == active_expected
                            if member_mode:
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s", (project,)).fetchone()[0] == 52
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s AND state='REMOVED'", (project,)).fetchone()[0] == 1
                                print("PROJECT_MEMBER_BROWSER_DATABASE PASS: 52 history, 51 active, one removed", flush=True)
                            if expected == 3:
                                if "--create-browser" in sys.argv[1:]:
                                    created = db.execute("SELECT project_id FROM plm.prj_projects WHERE project_code_normalized='create-p04'").fetchone()[0]
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s AND user_id=%s AND project_role='PROJECT_MANAGER'", (created, manager)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_CREATED'", (created,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id=%s AND state='COMPLETED'", (created,)).fetchone()[0] == 1
                            if state_mode:
                                assert db.execute("SELECT state,lock_version FROM plm.auth_users WHERE user_id=%s", (member,)).fetchone() == ("ENABLED", 2)
                                assert db.execute("SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NOT NULL", (member,)).fetchone()[0] >= 1
                                assert db.execute("SELECT count(*) FROM plm.auth_user_state_results WHERE user_id=%s", (member,)).fetchone()[0] == 2
                                print("USER_STATE_BROWSER_DATABASE PASS: target ENABLED/v2, old member session revoked, two immutable results", flush=True)
                            if name_mode:
                                renamed = "Synthetic Project Renamed Member"
                                assert db.execute("SELECT username_display,username_normalized,state,lock_version FROM plm.auth_users WHERE user_id=%s", (member,)).fetchone() == (renamed, renamed.lower(), "ENABLED", 1)
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='USER_NAME_CHANGED'", (member,)).fetchone()[0] == 1
                                print("USER_NAME_BROWSER_DATABASE PASS: same user renamed/v1, one audit event", flush=True)
                        print(f"PROJECT_BROWSER_DATABASE_COUNTS PASS: {expected} projects, {session_count} sessions, {active_expected} active members", flush=True)
                finally:
                    if proxy:
                        if proxy.poll() is None:
                            try:
                                proxy.stdin.write("STOP\n")
                                proxy.stdin.flush()
                                proxy.wait(timeout=10)
                            except (BrokenPipeError, subprocess.TimeoutExpired):
                                proxy.kill()
                                proxy.wait(timeout=10)
                        proxy.stdin.close()
                        proxy.stdout.close()
                    if server:
                        server.should_exit = True
                    if thread:
                        thread.join(timeout=10)
                        assert not thread.is_alive(), "Owned backend did not stop"
                    if sock:
                        sock.close()
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
        library.CredFree.argtypes = [ctypes.c_void_p]
        library.CredFree(pointer)
    assert not found and ctypes.get_last_error() == 1168
    print("PROJECT_BROWSER_FIXTURE_CLEANUP PASS: owned services stopped; database/role absent; Vault absence1168", flush=True)


if __name__ == "__main__":
    main()
