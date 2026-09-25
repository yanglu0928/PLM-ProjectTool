"""Disposable Windows Vault -> PostgreSQL -> real Project login proof."""

from __future__ import annotations

import ctypes
import tempfile
import uuid
from ctypes import wintypes
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
                    with connect(dbname) as db:
                        assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 1
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_ISSUED'").fetchone()[0] == 1
                    print("PASS: Windows Vault, real PostgreSQL login, Project summary, Cookie/CSRF, denial and Audit")
                finally:
                    delete_test_credential(target)
            finally:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        finally:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


if __name__ == "__main__":
    main()
