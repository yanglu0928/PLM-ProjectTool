"""Disposable PostgreSQL verification for guarded Department deactivation."""

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
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.deactivate_department import create_project_department_deactivate_router
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_member_create_access import SqlAlchemyProjectMemberCreateAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.create_member import (
    CreateProjectMember, ProjectMemberCreateError, ProjectMemberCreateService,
)
from plm_assistant.modules.project.application.deactivate_department import (
    DeactivateProjectDepartment, ProjectDepartmentDeactivateError,
    ProjectDepartmentDeactivateService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.department_deactivate_repository import SqlAlchemyProjectDepartmentDeactivateRepository
from plm_assistant.modules.project.infrastructure.member_create_repository import SqlAlchemyProjectMemberCreateRepository


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
        self.valid = True

    def require_valid(self, **_):
        if not self.valid:
            raise RuntimeLicenseError("EXPIRED")


class Sessions:
    def __init__(self, tokens):
        self.tokens = tokens

    def validate(self, token, *, csrf_token, require_csrf):
        if token not in self.tokens or csrf_token != CSRF or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def denied(code, operation):
    try:
        operation()
    except ProjectDepartmentDeactivateError as exc:
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
    name = "prj03a04_" + uuid.uuid4().hex[:12]
    token, other_token, cm_token = b"p" * 32, b"o" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            migration = create_migration_config(url)
            command.upgrade(migration, "20260925_0018")
            with connect(name) as existing_db:
                user(existing_db, "Synthetic Existing Before Upgrade")
            command.upgrade(migration, "head")
            with connect(name) as upgraded:
                assert upgraded.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 1
                assert upgraded.execute("SELECT count(*) FROM plm.prj_department_deactivate_results").fetchone()[0] == 0
            command.downgrade(migration, "20260925_0018")
            command.upgrade(migration, "head")
            command.check(migration)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = user(db, "Synthetic Manager", token)
                    other_pm = user(db, "Synthetic Other Manager", other_token)
                    cm = user(db, "Synthetic Customer Manager", cm_token)
                    active_user = user(db, "Synthetic Active")
                    suspended_user = user(db, "Synthetic Suspended")
                    removed_user = user(db, "Synthetic Removed")
                    race_user = user(db, "Synthetic Race")
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (other_pm,)).fetchone()[0]
                    deps = {}
                    for key in ("owner", "active", "suspended", "removed", "free", "race"):
                        code = key.upper()
                        deps[key] = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,%s,%s,%s) RETURNING department_id", (p1, code, key, "Synthetic " + key)).fetchone()[0]
                    foreign = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'FOREIGN','foreign','Foreign') RETURNING department_id", (p2,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p1, pm, deps["owner"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, other_pm, foreign))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')", (p1, cm, deps["owner"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')", (p1, active_user, deps["active"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role,state) VALUES (%s,%s,%s,'CUSTOMER_MEMBER','SUSPENDED')", (p1, suspended_user, deps["suspended"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role,state,ended_at) VALUES (%s,%s,%s,'CUSTOMER_MEMBER','REMOVED',statement_timestamp())", (p1, removed_user, deps["removed"]))
                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                common = dict(unit_of_work=runtime.unit_of_work, license_guard=guard,
                              authorization=authorization, clock=lambda: datetime.now(timezone.utc))
                deactivation_kwargs = dict(
                    **common, access=SqlAlchemyProjectWriteAccess(),
                    repository=SqlAlchemyProjectDepartmentDeactivateRepository(),
                )
                service = ProjectDepartmentDeactivateService(
                    **deactivation_kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                )
                idempotent = ProjectDepartmentDeactivateService(
                    **deactivation_kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                )
                member_service = ProjectMemberCreateService(
                    **common, access=SqlAlchemyProjectMemberCreateAccess(),
                    repository=SqlAlchemyProjectMemberCreateRepository(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def deactivate(key, *, actor=token, project=p1, version=0, client=service):
                    department_id = deps[key] if key in deps else foreign
                    return client.deactivate(DeactivateProjectDepartment(
                        actor, CSRF, uuid.uuid4(), project, department_id, version,
                    ))

                denied("PROJECT_DEPARTMENT_IN_USE", lambda: deactivate("owner"))
                denied("PROJECT_DEPARTMENT_IN_USE", lambda: deactivate("active"))
                denied("PROJECT_DEPARTMENT_IN_USE", lambda: deactivate("suspended"))
                denied("RESOURCE_NOT_FOUND", lambda: deactivate("foreign"))
                denied("RESOURCE_NOT_FOUND", lambda: deactivate("free", actor=cm_token))
                guard.valid = False
                try:
                    deactivate("free")
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("License failure bypassed")
                guard.valid = True
                removed = deactivate("removed")
                assert (removed.state, removed.etag) == ("INACTIVE", '"v1"')
                denied("CONFLICT_VERSION", lambda: deactivate("removed"))
                denied("CONFLICT_STATE", lambda: deactivate("removed", version=1))
                failed = ProjectDepartmentDeactivateService(**deactivation_kwargs, audit=FailedAudit())
                try:
                    deactivate("free", client=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_departments WHERE department_id=%s", (deps["free"],)).fetchone() == ("ACTIVE", 0)
                    assert db.execute("SELECT action,before_state,after_state FROM plm.aud_events WHERE target_object_id=%s", (deps["removed"],)).fetchone() == ("PROJECT_DEPARTMENT_DEACTIVATED", "ACTIVE", "INACTIVE")

                idem_command = DeactivateProjectDepartment(
                    token, CSRF, uuid.uuid4(), p1, deps["free"], 0,
                )
                first = idempotent.deactivate_idempotent(
                    idem_command, idempotency_key="department-deactivate-first-001",
                )
                assert (first.state, first.etag) == ("INACTIVE", '"v1"')
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_departments SET name='Changed After Deactivation' WHERE department_id=%s", (deps["free"],))
                assert idempotent.deactivate_idempotent(
                    idem_command, idempotency_key="department-deactivate-first-001",
                ) == first
                denied("CONFLICT_IDEMPOTENCY", lambda: idempotent.deactivate_idempotent(
                    DeactivateProjectDepartment(token, CSRF, uuid.uuid4(), p1, deps["free"], 1),
                    idempotency_key="department-deactivate-first-001",
                ))
                denied("RESOURCE_NOT_FOUND", lambda: idempotent.deactivate_idempotent(
                    DeactivateProjectDepartment(cm_token, CSRF, uuid.uuid4(), p1, deps["free"], 0),
                    idempotency_key="department-deactivate-first-001",
                ))
                guard.valid = False
                try:
                    idempotent.deactivate_idempotent(
                        idem_command, idempotency_key="department-deactivate-first-001",
                    )
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("License failure bypassed on replay")
                guard.valid = True
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_DEACTIVATED'", (deps["free"],)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.prj_department_deactivate_results WHERE department_id=%s", (deps["free"],)).fetchone()[0] == 1
                    try:
                        db.execute("UPDATE plm.prj_department_deactivate_results SET name='Tampered' WHERE department_id=%s", (deps["free"],))
                    except psycopg.errors.RaiseException:
                        pass
                    else:
                        raise AssertionError("deactivate snapshot unexpectedly mutable")

                with connect(name) as db:
                    concurrent = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'CONCURRENT','concurrent','Concurrent') RETURNING department_id", (p1,)).fetchone()[0]
                concurrent_command = DeactivateProjectDepartment(
                    token, CSRF, uuid.uuid4(), p1, concurrent, 0,
                )
                with ThreadPoolExecutor(max_workers=2) as pool:
                    repeated = list(pool.map(lambda _: idempotent.deactivate_idempotent(
                        concurrent_command, idempotency_key="department-deactivate-concurrent-001",
                    ), range(2)))
                assert repeated[0] == repeated[1]
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_DEACTIVATED'", (concurrent,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.prj_department_deactivate_results WHERE department_id=%s", (concurrent,)).fetchone()[0] == 1

                with connect(name) as db:
                    rollback = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'ROLLBACK','rollback','Rollback') RETURNING department_id", (p1,)).fetchone()[0]
                failed_idempotent = ProjectDepartmentDeactivateService(
                    **deactivation_kwargs, audit=FailedAudit(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                )
                try:
                    failed_idempotent.deactivate_idempotent(
                        DeactivateProjectDepartment(token, CSRF, uuid.uuid4(), p1, rollback, 0),
                        idempotency_key="department-deactivate-rollback-001",
                    )
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("idempotent Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_departments WHERE department_id=%s", (rollback,)).fetchone() == ("ACTIVE", 0)
                    assert db.execute("SELECT count(*) FROM plm.prj_department_deactivate_results WHERE department_id=%s", (rollback,)).fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_PROJECT_DEPARTMENT_DEACTIVATE' AND project_id=%s AND result_ref_id IS NULL", (p1,)).fetchone()[0] == 0

                with connect(name) as db:
                    http_department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HTTP-DEACTIVATE','http-deactivate','HTTP Department') RETURNING department_id", (p1,)).fetchone()[0]
                router = create_project_department_deactivate_router(
                    sessions=Sessions((token, other_token, cm_token)), departments=idempotent,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                path = f"/api/v1/projects/{p1}/departments/{http_department}:deactivate"
                headers = {
                    "origin": "https://plm.example.test",
                    "cookie": "plm_session=" + token.hex(),
                    "x-csrf-token": CSRF.hex(), "if-match": '"v0"',
                    "idempotency-key": "department-http-deactivate-001",
                }
                with TestClient(create_app(), base_url="https://plm.example.test") as bare:
                    assert bare.post(path, headers=headers).status_code == 404
                with TestClient(create_app(project_department_deactivate_router=router),
                                base_url="https://plm.example.test") as http:
                    first_http = http.post(path, headers=headers)
                    replay_http = http.post(path, headers=headers)
                    assert first_http.status_code == replay_http.status_code == 200, (first_http.text, replay_http.text)
                    assert first_http.json()["data"] == replay_http.json()["data"]
                    assert first_http.headers["etag"] == '"v1"'
                    assert http.post(path, headers={**headers, "if-match": '"v1"'}).status_code == 409
                    assert http.post(path, headers={**headers, "cookie": "plm_session=" + cm_token.hex()}).status_code == 404
                    assert http.post(f"/api/v1/projects/{p1}/departments/{deps['active']}:deactivate",
                                     headers={**headers, "idempotency-key": "department-http-inuse-001"}).status_code == 409
                    guard.valid = False
                    assert http.post(path, headers=headers).status_code == 403
                    guard.valid = True
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_DEACTIVATED'", (http_department,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.prj_department_deactivate_results WHERE department_id=%s", (http_department,)).fetchone()[0] == 1

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
                    for factory, suffix in (
                        (create_production_platform_app, "read"),
                        (create_production_platform_write_app, "write"),
                    ):
                        with connect(name) as db:
                            platform_department = db.execute(
                                "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,%s,%s,%s) RETURNING department_id",
                                (p1, f"PLATFORM-{suffix.upper()}", f"platform-{suffix}", f"Platform {suffix}"),
                            ).fetchone()[0]
                        production = factory(settings)
                        with TestClient(production, base_url="http://localhost") as client:
                            platform_path = f"/api/v1/projects/{p1}/departments/{platform_department}:deactivate"
                            platform_headers = {
                                "origin": "http://localhost",
                                "cookie": "plm_session=" + token.hex(),
                                "x-csrf-token": CSRF.hex(), "if-match": '"v0"',
                                "idempotency-key": f"department-platform-deactivate-{suffix}-001",
                            }
                            first_platform = client.post(platform_path, headers=platform_headers)
                            replay_platform = client.post(platform_path, headers=platform_headers)
                            assert first_platform.status_code == replay_platform.status_code == 200, (first_platform.text, replay_platform.text)
                            assert first_platform.json()["data"] == replay_platform.json()["data"]
                            assert first_platform.headers["etag"] == '"v1"'
                            assert client.post(platform_path, headers={**platform_headers,
                                               "cookie": "plm_session=" + cm_token.hex()}).status_code == 404
                            guard.valid = False
                            assert client.post(platform_path, headers=platform_headers).status_code == 403
                            guard.valid = True
                        with connect(name) as db:
                            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_DEPARTMENT_DEACTIVATED'", (platform_department,)).fetchone()[0] == 1
                            assert db.execute("SELECT count(*) FROM plm.prj_department_deactivate_results WHERE department_id=%s", (platform_department,)).fetchone()[0] == 1
                    with mock_patch("plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                                    side_effect=RuntimeError("synthetic missing department key")):
                        try:
                            create_production_platform_app(settings)
                        except Exception as exc:
                            assert str(exc) == "production login unavailable"
                        else:
                            raise AssertionError("missing trust source did not fail closed")

                def compete_deactivate():
                    try:
                        return deactivate("race").state
                    except ProjectDepartmentDeactivateError as exc:
                        return exc.code

                def compete_assign():
                    try:
                        return member_service.create(CreateProjectMember(
                            token, CSRF, uuid.uuid4(), p1, race_user,
                            "CUSTOMER_MEMBER", deps["race"],
                        )).state
                    except ProjectMemberCreateError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda fn: fn(), (compete_deactivate, compete_assign)))
                assert outcomes in (["INACTIVE", "PROJECT_ROLE_INVALID"],
                                    ["PROJECT_DEPARTMENT_IN_USE", "ACTIVE"]), outcomes
                with connect(name) as db:
                    state = db.execute("SELECT state FROM plm.prj_departments WHERE department_id=%s", (deps["race"],)).fetchone()[0]
                    active_members = db.execute("SELECT count(*) FROM plm.prj_project_members WHERE department_id=%s AND state IN ('ACTIVE','SUSPENDED')", (deps["race"],)).fetchone()[0]
                    assert (state == "INACTIVE" and active_members == 0) or (state == "ACTIVE" and active_members == 1)
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: deactivate("free"))
                assert idempotent.deactivate_idempotent(
                    idem_command, idempotency_key="department-deactivate-first-001",
                ) == first
                try:
                    command.downgrade(migration, "20260925_0018")
                except RuntimeError as exc:
                    assert "department deactivate results exist" in str(exc)
                else:
                    raise AssertionError("nonempty deactivate result downgrade should fail")
                print("PASS: migration/ORM, idempotent Department internal, optional HTTP and both Windows platform modes; replay/concurrency/rollback, member-in-use and archived denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
