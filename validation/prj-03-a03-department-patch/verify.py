"""Disposable PostgreSQL verification for scoped Department PATCH."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch as mock_patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    create_production_platform_app, create_production_platform_write_app,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.patch_department import create_project_department_patch_router

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.patch_department import (
    PatchProjectDepartment, ProjectDepartmentPatchError, ProjectDepartmentPatchService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.department_patch_repository import SqlAlchemyProjectDepartmentPatchRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


class Guard:
    def __init__(self):
        self.valid = True

    def require_valid(self, **_):
        if not self.valid:
            raise RuntimeLicenseError("EXPIRED")


class Sessions:
    def __init__(self, tokens):
        self.tokens = tokens

    def validate(self, token, *, csrf_token, require_csrf):
        if token not in self.tokens.values() or csrf_token != CSRF or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def denied(code, operation):
    try:
        operation()
    except ProjectDepartmentPatchError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


from unittest.mock import patch as audit_key_patch
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec


from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec as AuditRegressionDocumentCursor
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec as AuditRegressionVersionCursor
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec as AuditRegressionParseCursor
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer as AuditRegressionUploadIssuer
from types import SimpleNamespace as AuditRegressionKeys


@audit_key_patch("plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",new=lambda:AuditRegressionUploadIssuer(provider=AuditRegressionKeys(resolve_key=lambda ref:b"u"*32),key_ref="document-upload-token-v1"))
@audit_key_patch("plm_assistant.entrypoints.production_login.create_windows_document_list_cursor_codec",new=lambda:AuditRegressionDocumentCursor(b"l"*32))
@audit_key_patch("plm_assistant.entrypoints.production_login.create_windows_document_version_cursor_codec",new=lambda:AuditRegressionVersionCursor(b"v"*32))
@audit_key_patch("plm_assistant.entrypoints.production_login.create_windows_document_parse_cursor_codec",new=lambda:AuditRegressionParseCursor(b"p"*32))
@audit_key_patch("plm_assistant.entrypoints.production_login.create_windows_audit_cursor_codec",new=lambda:AuditListCursorCodec(b"a"*32))
def main():
    name = "prj03a03_" + uuid.uuid4().hex[:12]
    tokens = {"pm": b"p" * 32, "cm": b"m" * 32, "other": b"o" * 32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    ids = {key: user(db, "Synthetic " + key.upper(), token) for key, token in tokens.items()}
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (ids["pm"],)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (ids["other"],)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p1,)).fetchone()[0]
                    d3 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D3','d3','Other') RETURNING department_id", (p2,)).fetchone()[0]
                    inactive = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name,state) VALUES (%s,'D4','d4','Past','INACTIVE') RETURNING department_id", (p1,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p1, ids["pm"], d1))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')", (p1, ids["cm"], d1))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, ids["other"], d3))
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectDepartmentPatchRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = ProjectDepartmentPatchService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def patch(*, department=d2, project=p1, version=0, code=None,
                          name_value=None, actor="pm", csrf=CSRF, client=service):
                    return client.patch(PatchProjectDepartment(
                        tokens[actor], csrf, uuid.uuid4(), project, department,
                        version, code=code, name=name_value,
                    ))

                denied("AUTH_ACCESS_DENIED", lambda: patch(name_value="Name", csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: patch(name_value="Name", actor="cm"))
                denied("RESOURCE_NOT_FOUND", lambda: patch(department=d3, name_value="Name"))
                guard.valid = False
                try:
                    patch(name_value="Name")
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("License failure bypassed")
                guard.valid = True
                denied("CONFLICT_DUPLICATE", lambda: patch(code="D1"))
                denied("CONFLICT_STATE", lambda: patch(department=inactive, name_value="Past changed"))
                changed = patch(code="  ＮＥＷ  ", name_value="  新部门  ")
                assert (changed.code, changed.name, changed.etag) == ("NEW", "新部门", '"v1"')
                denied("CONFLICT_VERSION", lambda: patch(code="OLD"))
                noop = patch(version=1, code="NEW", name_value="新部门")
                assert noop.etag == '"v1"'
                with connect(name) as db:
                    assert db.execute("SELECT department_code_normalized,lock_version FROM plm.prj_departments WHERE department_id=%s", (d2,)).fetchone() == ("new", 1)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_PATCHED'", (d2,)).fetchone()[0] == 1
                router = create_project_department_patch_router(
                    sessions=Sessions(tokens), departments=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                path = f"/api/v1/projects/{p1}/departments/{d2}"
                headers = {
                    "origin": "https://plm.example.test",
                    "cookie": "plm_session=" + tokens["pm"].hex(),
                    "x-csrf-token": CSRF.hex(), "if-match": '"v1"',
                }
                with TestClient(create_app(), base_url="https://plm.example.test") as bare:
                    assert bare.patch(path, headers=headers, json={"name": "HTTP"}).status_code == 404
                with TestClient(create_app(project_department_patch_router=router),
                                base_url="https://plm.example.test") as http:
                    response = http.patch(path, headers=headers, json={"name": "HTTP"})
                    assert response.status_code == 200, response.text
                    assert response.headers["etag"] == '"v2"'
                    assert response.json()["data"]["name"] == "HTTP"
                    assert http.patch(path, headers=headers, json={"name": "Stale"}).status_code == 409
                    assert http.patch(f"/api/v1/projects/{p1}/departments/{d3}", headers=headers,
                                      json={"name": "Other"}).status_code == 404
                    cm_headers = {**headers, "cookie": "plm_session=" + tokens["cm"].hex(),
                                  "if-match": '"v2"'}
                    assert http.patch(path, headers=cm_headers, json={"name": "Denied"}).status_code == 404
                    guard.valid = False
                    assert http.patch(path, headers={**headers, "if-match": '"v2"'},
                                      json={"name": "Denied"}).status_code == 403
                    guard.valid = True
                    noop = http.patch(path, headers={**headers, "if-match": '"v2"'},
                                      json={"name": "HTTP"})
                    assert noop.status_code == 200 and noop.headers["etag"] == '"v2"'
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_departments WHERE department_id=%s", (d2,)).fetchone() == ("HTTP", 2)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_PATCHED'", (d2,)).fetchone()[0] == 2
                    platform_department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'PATCH-PLATFORM','patch-platform','Before') RETURNING department_id",
                        (p1,),
                    ).fetchone()[0]
                settings = BootstrapSettings(data_root=Path.cwd(), trusted_origins=("http://localhost",))
                with mock_patch("plm_assistant.entrypoints.production_login.read_database_url",
                                return_value=url), mock_patch(
                                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                                return_value=SimpleNamespace(guard=guard)), mock_patch(
                                "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                                return_value=SecretListCursorCodec(b"q" * 32)), mock_patch(
                                "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                                return_value=MemberListCursorCodec(b"m" * 32)), mock_patch(
                                "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                                return_value=DepartmentListCursorCodec(b"d" * 32)), mock_patch(
                                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                                return_value=Mock()):
                    for version, factory in enumerate((create_production_platform_app,
                                                       create_production_platform_write_app)):
                        production = factory(settings)
                        with TestClient(production, base_url="http://localhost") as client:
                            platform_path = f"/api/v1/projects/{p1}/departments/{platform_department}"
                            platform_headers = {
                                "origin": "http://localhost",
                                "cookie": "plm_session=" + tokens["pm"].hex(),
                                "x-csrf-token": CSRF.hex(), "if-match": f'"v{version}"',
                            }
                            new_name = f"Platform {version}"
                            response = client.patch(platform_path, headers=platform_headers,
                                                    json={"name": new_name})
                            assert response.status_code == 200, response.text
                            assert response.headers["etag"] == f'"v{version + 1}"'
                            assert client.patch(platform_path, headers=platform_headers,
                                                json={"name": "Stale"}).status_code == 409
                            assert client.patch(platform_path, headers={
                                **platform_headers, "cookie": "plm_session=" + tokens["cm"].hex(),
                                "if-match": f'"v{version + 1}"',
                            }, json={"name": "Denied"}).status_code == 404
                            guard.valid = False
                            assert client.patch(platform_path, headers={
                                **platform_headers, "if-match": f'"v{version + 1}"',
                            }, json={"name": "Denied"}).status_code == 403
                            guard.valid = True
                    with mock_patch("plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                                    side_effect=RuntimeError("synthetic missing department key")):
                        try:
                            create_production_platform_app(settings)
                        except Exception as exc:
                            assert str(exc) == "production login unavailable"
                        else:
                            raise AssertionError("missing trust source did not fail closed")
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_departments WHERE department_id=%s", (platform_department,)).fetchone() == ("Platform 1", 2)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_PATCHED'", (platform_department,)).fetchone()[0] == 2
                failed = ProjectDepartmentPatchService(**kwargs, audit=FailedAudit())
                try:
                    patch(version=2, name_value="Rollback", client=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_departments WHERE department_id=%s", (d2,)).fetchone() == ("HTTP", 2)
                def competing(args):
                    department_id, version = args
                    try:
                        return patch(department=department_id, version=version, code="SHARED").department_id
                    except ProjectDepartmentPatchError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(competing, ((d1, 0), (d2, 2))))
                assert len([item for item in outcomes if isinstance(item, uuid.UUID)]) == 1, outcomes
                assert outcomes.count("CONFLICT_DUPLICATE") == 1, outcomes
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s AND department_code_normalized='shared' AND state='ACTIVE'", (p1,)).fetchone()[0] == 1
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: patch(version=2, name_value="Blocked"))
                print("PASS: Department internal, optional HTTP and both Windows platform modes; role/scope/CSRF/License, version/noop, concurrency and Audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
