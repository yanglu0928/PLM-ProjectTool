"""Disposable Windows Vault -> PostgreSQL -> real Project login proof."""

from __future__ import annotations

import ctypes
import concurrent.futures
import tempfile
import uuid
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import create_production_login_app
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.windows_database_credential import write_database_url


HOST, PORT, ADMIN = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=ADMIN, dbname=name, autocommit=True)


def delete_test_credential(target: str) -> None:
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    library.CredDeleteW.restype = wintypes.BOOL
    library.CredDeleteW(target, 1, 0)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    dbname, role = f"aut03a07p03_{suffix}", f"aut03a07p03_{suffix}"
    password = uuid.uuid4().hex + uuid.uuid4().hex
    target = f"PLMProjectTool/Test-{uuid.uuid4()}"
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
            sql.Identifier(role), sql.Literal(password)))
        try:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(dbname), sql.Identifier(role)))
            try:
                url = URL.create("postgresql+psycopg", username=role, password=password,
                                 host=HOST, port=PORT, database=dbname)
                with connect(dbname) as db:
                    db.execute("CREATE EXTENSION IF NOT EXISTS vector")
                command.upgrade(create_migration_config(url), "head")
                with connect(dbname) as db:
                    db.execute(sql.SQL("GRANT USAGE ON SCHEMA plm TO {}").format(sql.Identifier(role)))
                clear = bytearray(b"synthetic-login-password")
                view = memoryview(clear)
                try:
                    hashed = ScryptPasswordHasher().hash_password(view)
                finally:
                    view.release()
                    clear[:] = b"\x00" * len(clear)
                with connect(dbname) as db:
                    user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                                      "VALUES ('Synthetic Member','synthetic member') RETURNING user_id").fetchone()[0]
                    credential = db.execute(
                        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
                        "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
                        (user, hashed.password_hash, hashed.algorithm_id,
                         '{"n":131072,"r":8,"p":1,"dklen":32}'),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                               (credential, user))
                    project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('P1','p1','Synthetic Project',%s) RETURNING project_id", (user,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'D1','d1','Synthetic Department') RETURNING department_id", (project,),
                    ).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                               "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, user, department))
                write_database_url(url.render_as_string(hide_password=False), target=target)
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        settings = BootstrapSettings(data_root=Path(directory), trusted_origins=("http://localhost",))
                        app = create_production_login_app(settings, credential_target=target)
                        with TestClient(create_app(), base_url="http://localhost") as bare:
                            assert bare.post("/api/v1/auth/login").status_code == 404
                            assert bare.get("/api/v1/auth/session").status_code == 404
                        with TestClient(app, base_url="http://localhost",
                                        client=(HOST, 50000)) as client:
                            assert client.get("/health/ready").status_code == 200
                            body = {"username": "Synthetic Member", "password": "synthetic-login-password"}
                            assert client.post("/api/v1/auth/login", headers={"origin": "http://evil.test"},
                                               json=body).status_code == 403
                            wrong = client.post("/api/v1/auth/login", headers={"origin": "http://localhost"},
                                                json={**body, "password": "wrong-password"})
                            assert wrong.status_code == 401 and "set-cookie" not in wrong.headers
                            good = client.post("/api/v1/auth/login", headers={"origin": "http://localhost"},
                                               json=body)
                            assert good.status_code == 200, good.text
                            assert good.json()["data"]["authorized_projects"] == [
                                {"project_id": str(project), "name": "Synthetic Project", "role": "PROJECT_MANAGER"}
                            ]
                            assert len(good.json()["data"]["csrf_token"]) == 64
                            assert "HttpOnly" in good.headers["set-cookie"]
                            assert "synthetic-login-password" not in good.text
                            current = client.get("/api/v1/auth/session")
                            assert current.status_code == 200, current.text
                            assert current.json()["data"]["authorized_projects"] == good.json()["data"]["authorized_projects"]
                            assert "csrf_token" not in current.text and "set-cookie" not in current.headers
                            with connect(dbname) as db:
                                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_id=%s AND user_id=%s",
                                           (project, user))
                            refreshed = client.get("/api/v1/auth/session")
                            assert refreshed.status_code == 200 and refreshed.json()["data"]["authorized_projects"] == []
                            old_cookie = good.cookies["plm_session"]
                            old_csrf = good.json()["data"]["csrf_token"]
                            renewed = client.post("/api/v1/auth/session:renew", headers={
                                "origin": "http://localhost", "x-csrf-token": old_csrf,
                            })
                            assert renewed.status_code == 200, renewed.text
                            assert renewed.cookies["plm_session"] != old_cookie
                            assert renewed.json()["data"]["csrf_token"] != old_csrf
                            assert datetime.fromisoformat(renewed.json()["data"]["absolute_expires_at"]) == datetime.fromisoformat(
                                good.json()["data"]["absolute_expires_at"]
                            )
                            assert renewed.json()["data"]["authorized_projects"] == []
                            old_read = client.get("/api/v1/auth/session", headers={
                                "cookie": "plm_session=" + old_cookie,
                            })
                            assert old_read.status_code == 401
                            assert client.get("/api/v1/auth/session").status_code == 200
                            logout_key = "synthetic-logout-key-1234"
                            logout_headers = {
                                "origin": "http://localhost",
                                "x-csrf-token": renewed.json()["data"]["csrf_token"],
                                "idempotency-key": logout_key,
                            }
                            latest_cookie = renewed.cookies["plm_session"]
                            logout = client.post("/api/v1/auth/logout", headers=logout_headers)
                            assert logout.status_code == 200, logout.text
                            assert logout.json()["data"] == {"revoked": True}
                            assert "Max-Age=0" in logout.headers["set-cookie"]
                            retry_headers = {**logout_headers, "cookie": "plm_session=" + latest_cookie}
                            assert client.post("/api/v1/auth/logout", headers=retry_headers).status_code == 200
                            assert client.get("/api/v1/auth/session", headers={
                                "cookie": "plm_session=" + latest_cookie,
                            }).status_code == 401
                            assert client.post("/api/v1/auth/logout", headers={
                                **retry_headers, "idempotency-key": "synthetic-different-key-1234",
                            }).status_code == 401
                            second_login = client.post("/api/v1/auth/login", headers={"origin": "http://localhost"},
                                                       json=body)
                            assert second_login.status_code == 200
                            conflict = client.post("/api/v1/auth/logout", headers={
                                **logout_headers,
                                "x-csrf-token": second_login.json()["data"]["csrf_token"],
                            })
                            assert conflict.status_code == 409
                            assert client.get("/api/v1/auth/session").status_code == 200
                            concurrent_headers = {
                                "origin": "http://localhost",
                                "x-csrf-token": second_login.json()["data"]["csrf_token"],
                                "idempotency-key": "synthetic-concurrent-logout-1234",
                                "cookie": "plm_session=" + second_login.cookies["plm_session"],
                            }
                            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                                outcomes = list(pool.map(
                                    lambda _: client.post("/api/v1/auth/logout", headers=concurrent_headers).status_code,
                                    range(2),
                                ))
                            assert outcomes == [200, 200], outcomes
                            assert client.get("/api/v1/auth/session", headers={
                                "cookie": concurrent_headers["cookie"],
                            }).status_code == 401
                    with connect(dbname) as db:
                        assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 3
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_ISSUED'").fetchone()[0] == 2
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_RENEWED'").fetchone()[0] == 1
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_REVOKED'").fetchone()[0] == 2
                        assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AUTH_LOGOUT'").fetchone()[0] == 2
                    print("PASS: Windows Vault, real PostgreSQL login/GET/renew/logout, exact replay/conflict, Cookie/CSRF, Project summary and Audit")
                finally:
                    delete_test_credential(target)
            finally:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        finally:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


if __name__ == "__main__":
    main()
