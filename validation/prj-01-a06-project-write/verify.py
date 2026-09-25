"""Disposable PostgreSQL proof of Project PATCH and one-way ARCHIVE."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch as mock_patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import create_production_platform_app
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.api.patch_project import create_project_patch_router
from plm_assistant.modules.project.application.write_project import (
    ArchiveProject, PatchProjectName, ProjectWriteError, ProjectWriteService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.write_repository import SqlAlchemyProjectWriteRepository

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF, MANAGER_TOKEN, OTHER_TOKEN, HTTP_TOKEN = b"c" * 32, b"m" * 32, b"o" * 32, b"h" * 32


class HttpSessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token not in (MANAGER_TOKEN, OTHER_TOKEN, HTTP_TOKEN) or csrf_token != CSRF or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


def denied(code, operation):
    try:
        operation()
    except ProjectWriteError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj01a06_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    manager = user(db, "Synthetic Manager", MANAGER_TOKEN)
                    other = user(db, "Synthetic Other", OTHER_TOKEN)
                    http_manager = user(db, "Synthetic HTTP Manager", HTTP_TOKEN)
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (manager,)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (manager,)).fetchone()[0]
                    p3 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P3','p3','HTTP Before',%s) RETURNING project_id", (http_manager,)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p2,)).fetchone()[0]
                    d3 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D3','d3','HTTP') RETURNING department_id", (p3,)).fetchone()[0]
                    m1 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager, d1)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, other, d2))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p3, http_manager, d3))
                guard = Guard()
                kwargs = dict(unit_of_work=runtime.unit_of_work,
                              access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                              authorization=ProjectAuthorizationService(
                                  unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyProjectAuthorizationRepository()),
                              repository=SqlAlchemyProjectWriteRepository(),
                              clock=lambda: datetime.now(timezone.utc))
                service = ProjectWriteService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))
                router = create_project_patch_router(
                    sessions=HttpSessions(), writes=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                with TestClient(create_app(project_patch_router=router), base_url="https://plm.example.test") as client:
                    path = f"/api/v1/projects/{p3}"
                    headers = {
                        "origin": "https://plm.example.test",
                        "cookie": "plm_session=" + HTTP_TOKEN.hex(),
                        "x-csrf-token": CSRF.hex(),
                        "if-match": '"v0"',
                    }
                    response = client.patch(path, headers=headers, json={"name": "HTTP After"})
                    assert response.status_code == 200, response.text
                    assert response.headers["etag"] == '"v1"'
                    assert response.json()["data"]["name"] == "HTTP After"
                    assert client.patch(path, headers=headers, json={"name": "Again"}).status_code == 409
                    cross = {**headers, "cookie": "plm_session=" + MANAGER_TOKEN.hex(), "if-match": '"v1"'}
                    assert client.patch(path, headers=cross, json={"name": "Hidden"}).status_code == 404
                    assert client.patch(path, headers={key: value for key, value in headers.items() if key != "if-match"}, json={"name": "Missing"}).status_code == 428
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_projects WHERE project_id=%s", (p3,)).fetchone() == ("HTTP After", 1)
                    assert db.execute("SELECT action FROM plm.aud_events WHERE target_project_id=%s", (p3,)).fetchall() == [("PROJECT_PATCHED",)]
                settings = BootstrapSettings(data_root=Path.cwd(), trusted_origins=("http://localhost",))
                with mock_patch("plm_assistant.entrypoints.production_login.read_database_url", return_value=url), mock_patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=SimpleNamespace(guard=guard),
                ), mock_patch(
                    "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                    return_value=SecretListCursorCodec(b"q" * 32),
                ):
                    production = create_production_platform_app(settings)
                    with TestClient(production, base_url="http://localhost") as client:
                        path = f"/api/v1/projects/{p3}"
                        headers = {
                            "origin": "http://localhost",
                            "cookie": "plm_session=" + HTTP_TOKEN.hex(),
                            "x-csrf-token": CSRF.hex(),
                            "if-match": '"v1"',
                        }
                        updated = client.patch(path, headers=headers, json={"name": "Production After"})
                        assert updated.status_code == 200, updated.text
                        assert updated.headers["etag"] == '"v2"'
                        assert client.patch(path, headers=headers, json={"name": "Stale"}).status_code == 409
                        guard.enabled = False
                        denied_prod = client.patch(path, headers={**headers, "if-match": '"v2"'}, json={"name": "Denied"})
                        assert denied_prod.status_code == 403, denied_prod.text
                        guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_projects WHERE project_id=%s", (p3,)).fetchone() == ("Production After", 2)
                    assert db.execute("SELECT action FROM plm.aud_events WHERE target_project_id=%s ORDER BY audit_event_id", (p3,)).fetchall() == [("PROJECT_PATCHED",), ("PROJECT_PATCHED",)]
                failed_idempotent = ProjectWriteService(
                    **kwargs, audit=FailedAudit(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                )
                archive_p2 = ArchiveProject(OTHER_TOKEN, CSRF, uuid.uuid4(), p2, 0)
                try:
                    failed_idempotent.archive_idempotent(
                        archive_p2, idempotency_key="project-archive-fail-0001",
                    )
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("archive Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_projects WHERE project_id=%s", (p2,)).fetchone() == ("ACTIVE", 0)
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s", (p2,)).fetchone()[0] == 0
                idempotent = ProjectWriteService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                )
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(
                        idempotent.archive_idempotent, archive_p2,
                        idempotency_key="project-archive-key-0001",
                    ) for _ in range(2)]
                    results = [future.result() for future in futures]
                assert [result.state for result in results] == ["ARCHIVED", "ARCHIVED"]
                assert [result.etag for result in results] == ['"v1"', '"v1"']
                denied("CONFLICT_IDEMPOTENCY", lambda: idempotent.archive_idempotent(
                    ArchiveProject(OTHER_TOKEN, CSRF, uuid.uuid4(), p2, 1),
                    idempotency_key="project-archive-key-0001",
                ))
                denied("PROJECT_ARCHIVED", lambda: idempotent.archive_idempotent(
                    archive_p2, idempotency_key="project-archive-key-0002",
                ))
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_projects WHERE project_id=%s", (p2,)).fetchone() == ("ARCHIVED", 1)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s AND action='PROJECT_ARCHIVED'", (p2,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s", (p2,)).fetchone()[0] == 1

                def patch(version=0, token=MANAGER_TOKEN, csrf=CSRF, target=service):
                    return target.patch_name(PatchProjectName(token, csrf, uuid.uuid4(), p1, version, " 新名称 "))

                def archive(version=1, target=service):
                    return target.archive(ArchiveProject(MANAGER_TOKEN, CSRF, uuid.uuid4(), p1, version))

                denied("AUTH_ACCESS_DENIED", lambda: patch(csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: patch(token=OTHER_TOKEN))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MANAGER' WHERE project_member_id=%s", (m1,))
                denied("RESOURCE_NOT_FOUND", patch)
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE project_member_id=%s", (m1,))
                guard.enabled = False
                try:
                    patch()
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("License rejection bypassed")
                guard.enabled = True
                failed = ProjectWriteService(**kwargs, audit=FailedAudit())
                try:
                    patch(target=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_projects WHERE project_id=%s", (p1,)).fetchone() == ("First", 0)
                first = patch()
                assert (first.name, first.etag) == ("新名称", '"v1"')
                denied("CONFLICT_VERSION", patch)
                archived = archive()
                assert (archived.state, archived.etag) == ("ARCHIVED", '"v2"')
                denied("PROJECT_ARCHIVED", lambda: patch(version=2))
                denied("PROJECT_ARCHIVED", lambda: archive(version=2))
                with connect(name) as db:
                    assert db.execute("SELECT state,name,lock_version FROM plm.prj_projects WHERE project_id=%s", (p1,)).fetchone() == ("ARCHIVED", "新名称", 2)
                    assert db.execute("SELECT action FROM plm.aud_events WHERE target_project_id=%s ORDER BY audit_event_id", (p1,)).fetchall() == [("PROJECT_PATCHED",), ("PROJECT_ARCHIVED",)]
                print("PASS: Project PATCH optional/Windows platform HTTP, real Session/DB, role isolation, License, ETag, Audit rollback and concurrent idempotent archive")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
