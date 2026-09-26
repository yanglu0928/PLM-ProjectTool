"""Disposable PostgreSQL verification for assignment PATCH and schema upgrade."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch as mock_patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    create_production_platform_app, create_production_platform_write_app,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.patch_member import create_project_member_patch_router
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.auth.infrastructure.project_member_patch_access import SqlAlchemyProjectMemberPatchAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.patch_member import (
    PatchProjectMember, ProjectMemberPatchError, ProjectMemberPatchService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_patch_repository import SqlAlchemyProjectMemberPatchRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token=None):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    if token is not None:
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return None


class HttpSessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token not in (b"p" * 32, b"m" * 32) or csrf_token != CSRF or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def denied(code, operation):
    try:
        operation()
    except ProjectMemberPatchError as exc:
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
    name = "prj02a03_" + uuid.uuid4().hex[:12]
    empty_name = "prj02a03_empty_" + uuid.uuid4().hex[:12]
    token = b"p" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(empty_name)))
        try:
            empty_url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=empty_name)
            empty_config = create_migration_config(empty_url)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            command.downgrade(empty_config, "20260925_0013")
            with connect(empty_name) as db:
                assert db.execute("SELECT to_regclass('plm.prj_member_assignment_history')").fetchone()[0] is None
            command.upgrade(empty_config, "head")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (empty_name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(empty_name)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "20260925_0013")
            with connect(name) as db:
                manager = user(db, "Synthetic Manager", token)
                customer_manager = user(db, "Synthetic Customer Manager", b"m" * 32)
                target = user(db, "Synthetic Target")
                http_target = user(db, "Synthetic HTTP Target")
                platform_target = user(db, "Synthetic Platform Target")
                platform_write_target = user(db, "Synthetic Platform Write Target")
                outsider = user(db, "Synthetic Outsider")
                p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (manager,)).fetchone()[0]
                p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (manager,)).fetchone()[0]
                d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First Department') RETURNING department_id", (p1,)).fetchone()[0]
                d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second Department') RETURNING department_id", (p1,)).fetchone()[0]
                other = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D3','d3','Other Department') RETURNING department_id", (p2,)).fetchone()[0]
                manager_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager, d1)).fetchone()[0]
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')", (p1, customer_manager, d1))
                member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id", (p1, target, d1)).fetchone()[0]
                http_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id", (p1, http_target, d1)).fetchone()[0]
                platform_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id", (p1, platform_target, d1)).fetchone()[0]
                platform_write_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id", (p1, platform_write_target, d1)).fetchone()[0]
                foreign_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p2, outsider, other)).fetchone()[0]
            command.upgrade(config, "head")  # existing-data upgrade
            command.check(config)
            runtime = create_database_runtime(url)
            try:
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectMemberPatchAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectMemberPatchRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = ProjectMemberPatchService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def patch(*, project=p1, member_id=member, version=0, role=None,
                          department=None, csrf=CSRF, target_token=token):
                    return service.patch(PatchProjectMember(
                        target_token, csrf, uuid.uuid4(), project, member_id,
                        version, role=role, department_id=department,
                    ))

                denied("AUTH_ACCESS_DENIED", lambda: patch(role="CUSTOMER_MEMBER", csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: patch(member_id=foreign_member, role="CUSTOMER_MEMBER"))
                denied("PROJECT_ROLE_INVALID", lambda: patch(department=other))
                denied("PROJECT_ROLE_INVALID", lambda: patch(member_id=manager_member, role="CUSTOMER_MEMBER"))
                first = patch(role="CUSTOMER_MEMBER", department=d2)
                assert (first.role, first.department_id, first.etag) == ("CUSTOMER_MEMBER", d2, '"v1"')
                denied("CONFLICT_VERSION", lambda: patch(role="IMPLEMENTATION_MEMBER"))
                noop = patch(version=1, role="CUSTOMER_MEMBER")
                assert noop.etag == '"v1"'
                router = create_project_member_patch_router(
                    sessions=HttpSessions(), members=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                with TestClient(create_app(project_member_patch_router=router),
                                base_url="http://localhost") as client:
                    path = f"/api/v1/projects/{p1}/members/{http_member}"
                    headers = {"origin": "http://localhost",
                               "cookie": "plm_session=" + token.hex(),
                               "x-csrf-token": CSRF.hex(), "if-match": '"v0"'}
                    body = {"role": "CUSTOMER_MEMBER", "department_id": str(d2)}
                    updated = client.patch(path, headers=headers, json=body)
                    assert updated.status_code == 200, updated.text
                    assert updated.headers["etag"] == '"v1"'
                    assert updated.json()["data"]["role"] == "CUSTOMER_MEMBER"
                    assert client.patch(path, headers=headers, json=body).status_code == 409
                    assert client.patch(f"/api/v1/projects/{p2}/members/{http_member}",
                                        headers=headers, json=body).status_code == 404
                    assert client.patch(f"/api/v1/projects/{p1}/members/{foreign_member}",
                                        headers=headers, json=body).status_code == 404
                    assert client.patch(path, headers={
                        **headers, "cookie": "plm_session=" + (b"m" * 32).hex(),
                        "if-match": '"v1"',
                    }, json={"role": "IMPLEMENTATION_MEMBER"}).status_code == 404
                    assert client.patch(f"/api/v1/projects/{p1}/members/{manager_member}",
                                        headers=headers, json={"role": "CUSTOMER_MEMBER"}).status_code == 422
                    guard.enabled = False
                    assert client.patch(path, headers={**headers, "if-match": '"v1"'},
                                        json={"role": "IMPLEMENTATION_MEMBER"}).status_code == 403
                    guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT project_role,department_id,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (http_member,)).fetchone() == ("CUSTOMER_MEMBER", d2, 1)
                    assert db.execute("SELECT count(*) FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (http_member,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_MEMBER_PATCHED'", (http_member,)).fetchone()[0] == 1
                settings = BootstrapSettings(
                    data_root=Path.cwd(), trusted_origins=("http://localhost",),
                )
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
                    for factory, member_id in (
                        (create_production_platform_app, platform_member),
                        (create_production_platform_write_app, platform_write_member),
                    ):
                        production = factory(settings)
                        with TestClient(production, base_url="http://localhost") as client:
                            url_path = f"/api/v1/projects/{p1}/members/{member_id}"
                            platform_headers = {"origin": "http://localhost",
                                                "cookie": "plm_session=" + token.hex(),
                                                "x-csrf-token": CSRF.hex(),
                                                "if-match": '"v0"'}
                            success = client.patch(url_path, headers=platform_headers,
                                                   json={"role": "CUSTOMER_MEMBER", "department_id": str(d2)})
                            assert success.status_code == 200, success.text
                            assert success.headers["etag"] == '"v1"'
                            assert client.patch(url_path, headers=platform_headers,
                                                json={"role": "IMPLEMENTATION_MEMBER"}).status_code == 409
                            assert client.patch(url_path, headers={
                                **platform_headers,
                                "cookie": "plm_session=" + (b"m" * 32).hex(),
                                "if-match": '"v1"',
                            }, json={"role": "IMPLEMENTATION_MEMBER"}).status_code == 404
                            guard.enabled = False
                            assert client.patch(url_path, headers={
                                **platform_headers, "if-match": '"v1"',
                            }, json={"role": "IMPLEMENTATION_MEMBER"}).status_code == 403
                            guard.enabled = True
                        with connect(name) as db:
                            assert db.execute("SELECT project_role,department_id,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (member_id,)).fetchone() == ("CUSTOMER_MEMBER", d2, 1)
                            assert db.execute("SELECT count(*) FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member_id,)).fetchone()[0] == 1
                            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_MEMBER_PATCHED'", (member_id,)).fetchone()[0] == 1
                    with mock_patch("plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                                    side_effect=RuntimeError("synthetic missing member key")):
                        try:
                            create_production_platform_app(settings)
                        except Exception as exc:
                            assert str(exc) == "production login unavailable"
                        else:
                            raise AssertionError("missing trust source did not fail closed")
                with connect(name) as db:
                    row = db.execute("SELECT before_role,after_role,before_department_id,after_department_id,before_version,after_version FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member,)).fetchone()
                    assert row == ("IMPLEMENTATION_MEMBER", "CUSTOMER_MEMBER", d1, d2, 0, 1), row
                    assert db.execute("SELECT count(*) FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_MEMBER_PATCHED'", (member,)).fetchone()[0] == 1
                failed = ProjectMemberPatchService(**kwargs, audit=FailedAudit())
                try:
                    failed.patch(PatchProjectMember(token, CSRF, uuid.uuid4(), p1, member, 1, role="IMPLEMENTATION_MEMBER"))
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT project_role,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (member,)).fetchone() == ("CUSTOMER_MEMBER", 1)
                    assert db.execute("SELECT count(*) FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member,)).fetchone()[0] == 1
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: patch(version=1, role="IMPLEMENTATION_MEMBER"))
                try:
                    command.downgrade(config, "20260925_0013")
                except RuntimeError as exc:
                    assert "empty history" in str(exc)
                else:
                    raise AssertionError("nonempty history downgrade should fail")
                print("PASS: optional and Windows platform/write PATCH, Session/If-Match/role/License, trust-source fail-closed, history/Audit and rollback guards")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
