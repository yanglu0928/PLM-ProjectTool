"""Disposable PostgreSQL proof of atomic Project bootstrap."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import create_production_platform_app
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_create_access import SqlAlchemyProjectCreateAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.project.application.create_project import (
    CreateProject, DepartmentSeed, ProjectCreateError, ProjectCreateService,
)
from plm_assistant.modules.project.api.create_project import create_project_create_router
from plm_assistant.modules.project.infrastructure.create_repository import SqlAlchemyProjectCreateRepository
from plm_assistant.modules.workflow.application.initialize import WorkflowInitializationService
from plm_assistant.modules.workflow.infrastructure.initialize_repository import SqlAlchemyWorkflowInitializationRepository
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF, ADMIN_TOKEN, NONADMIN_TOKEN = b"c" * 32, b"a" * 32, b"n" * 32


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


class HttpSessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if (token not in (ADMIN_TOKEN, NONADMIN_TOKEN) or csrf_token != CSRF
                or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, role, token=None):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role)).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    if token is not None:
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


def denied(service, code, command):
    try:
        service.create(command)
    except ProjectCreateError as exc:
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
    name = "prj01a04_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    admin_id = user(db, "Synthetic Admin", "DEPLOYMENT_ADMIN", ADMIN_TOKEN)
                    manager_id = user(db, "Synthetic Manager", "NONE")
                    other_id = user(db, "Synthetic Other", "NONE", NONADMIN_TOKEN)
                    disabled_id = user(db, "Synthetic Disabled", "NONE")
                    replay_manager_id = user(db, "Synthetic Replay Manager", "NONE")
                    rollback_manager_id = user(db, "Synthetic Rollback Manager", "NONE")
                    http_manager_id = user(db, "Synthetic HTTP Manager", "NONE")
                    production_manager_id = user(db, "Synthetic Production Manager", "NONE")
                    initializer_failure_manager = user(db, "Synthetic Initializer Rollback", "NONE")
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (disabled_id,))
                guard = Guard()
                kwargs = dict(unit_of_work=runtime.unit_of_work,
                              access=SqlAlchemyProjectCreateAccess(),
                              license_guard=guard,
                              repository=SqlAlchemyProjectCreateRepository(),
                              clock=lambda: datetime.now(timezone.utc),
                              workflow_initializer=WorkflowInitializationService(
                                  repository=SqlAlchemyWorkflowInitializationRepository(),
                                  audit=AuditService(SqlAlchemyAuditRepository()),
                              ))
                service = ProjectCreateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def cmd(code="P1", manager=manager_id, token=ADMIN_TOKEN, csrf=CSRF, dept=None):
                    return CreateProject(token, csrf, uuid.uuid4(), code, "Synthetic Project", manager, dept)

                denied(service, "AUTH_ACCESS_DENIED", cmd(token=NONADMIN_TOKEN))
                denied(service, "AUTH_ACCESS_DENIED", cmd(csrf=b"x" * 32))
                guard.enabled = False
                try:
                    service.create(cmd())
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("expired License allowed")
                guard.enabled = True
                denied(service, "PROJECT_MANAGER_INVALID", cmd(manager=disabled_id))
                created = service.create(cmd())
                with connect(name) as db:
                    p = db.execute("SELECT project_code,project_code_normalized,name,created_by FROM plm.prj_projects WHERE project_id=%s", (created.project_id,)).fetchone()
                    d = db.execute("SELECT department_code,name FROM plm.prj_departments WHERE department_id=%s", (created.department_id,)).fetchone()
                    m = db.execute("SELECT user_id,project_role,department_id FROM plm.prj_project_members WHERE project_member_id=%s", (created.project_member_id,)).fetchone()
                    a = db.execute("SELECT actor_id,action,target_project_id FROM plm.aud_events WHERE target_object_id=%s", (created.project_id,)).fetchone()
                    assert p == ("P1", "p1", "Synthetic Project", admin_id), p
                    assert d == ("DEFAULT", "默认部门"), d
                    assert m == (manager_id, "PROJECT_MANAGER", created.department_id), m
                    assert a == (admin_id, "PROJECT_CREATED", created.project_id), a
                    assert db.execute("SELECT workflow_state,current_stage_key FROM plm.wfl_project_workflows WHERE project_id=%s", (created.project_id,)).fetchone() == ("NOT_STARTED", None)
                    assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE user_id=%s", (admin_id,)).fetchone()[0] == 0
                denied(service, "PROJECT_CODE_CONFLICT", cmd("ｐ１", manager=other_id))
                denied(service, "PROJECT_USER_ALREADY_ASSIGNED", cmd("P2", manager=manager_id))
                failed = ProjectCreateService(**kwargs, audit=FailedAudit())
                try:
                    failed.create(cmd("P3", manager=other_id, dept=DepartmentSeed("D3", "Third")))
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure allowed")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_projects WHERE project_code_normalized='p3'").fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 1
                second = service.create(cmd("P2", manager=other_id, dept=DepartmentSeed("D2", "Second")))
                with connect(name) as db:
                    assert db.execute("SELECT department_code FROM plm.prj_departments WHERE department_id=%s", (second.department_id,)).fetchone()[0] == "D2"
                receipts = SqlAlchemyIdempotencyReceipts()
                idempotent = ProjectCreateService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()), receipts=receipts,
                )
                replay_command = cmd("P4", manager=replay_manager_id)
                replay_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(
                        lambda _: idempotent.create_idempotent(
                            replay_command, idempotency_key=replay_key,
                        ), range(2),
                    ))
                assert outcomes[0] == outcomes[1]
                assert (outcomes[0].code, outcomes[0].name,
                        outcomes[0].state, outcomes[0].etag) == (
                    "P4", "Synthetic Project", "ACTIVE", '"v0"',
                )
                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.prj_projects SET name='Later Name',state='ARCHIVED',lock_version=1 WHERE project_id=%s",
                        (outcomes[0].project_id,),
                    )
                assert idempotent.create_idempotent(
                    replay_command, idempotency_key=replay_key,
                ) == outcomes[0]
                try:
                    idempotent.create_idempotent(
                        cmd("P5", manager=replay_manager_id), idempotency_key=replay_key,
                    )
                except ProjectCreateError as exc:
                    assert exc.code == "CONFLICT_IDEMPOTENCY"
                else:
                    raise AssertionError("different Project payload reused one Key")
                with connect(name) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.prj_projects WHERE project_code_normalized='p4'"
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_CREATED'",
                        (outcomes[0].project_id,),
                    ).fetchone()[0] == 1
                failed_idempotent = ProjectCreateService(
                    **kwargs, audit=FailedAudit(), receipts=receipts,
                )
                rollback_command = cmd("P6", manager=rollback_manager_id)
                rollback_key = str(uuid.uuid4())
                try:
                    failed_idempotent.create_idempotent(
                        rollback_command, idempotency_key=rollback_key,
                    )
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("failed Audit committed Project")
                recovered = idempotent.create_idempotent(
                    rollback_command, idempotency_key=rollback_key,
                )
                with connect(name) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.prj_projects WHERE project_code_normalized='p6'"
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_CREATED'",
                        (recovered.project_id,),
                    ).fetchone()[0] == 1
                router = create_project_create_router(
                    sessions=HttpSessions(), projects=idempotent,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                with TestClient(create_app(project_create_router=router),
                                base_url="http://localhost") as client:
                    headers = {
                        "origin": "http://localhost",
                        "cookie": "plm_session=" + ADMIN_TOKEN.hex(),
                        "x-csrf-token": CSRF.hex(),
                        "idempotency-key": str(uuid.uuid4()),
                    }
                    body = {
                        "code": "P7", "name": "Synthetic HTTP Project",
                        "initial_manager_user_id": str(http_manager_id),
                    }
                    first = client.post("/api/v1/projects", headers=headers, json=body)
                    replay = client.post("/api/v1/projects", headers=headers, json=body)
                    assert first.status_code == replay.status_code == 201
                    assert first.json()["data"] == replay.json()["data"]
                    http_project_id = uuid.UUID(first.json()["data"]["project_id"])
                    assert first.headers["etag"] == '"v0"'
                    nonadmin = client.post("/api/v1/projects", headers={
                        **headers, "cookie": "plm_session=" + NONADMIN_TOKEN.hex(),
                        "idempotency-key": str(uuid.uuid4()),
                    }, json={**body, "code": "P8"})
                    assert nonadmin.status_code == 404
                    guard.enabled = False
                    denied_http = client.post("/api/v1/projects", headers={
                        **headers, "idempotency-key": str(uuid.uuid4()),
                    }, json={**body, "code": "P8"})
                    assert denied_http.status_code == 403
                    guard.enabled = True
                with connect(name) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.prj_projects WHERE project_code_normalized='p7'"
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_CREATED'",
                        (http_project_id,),
                    ).fetchone()[0] == 1
                settings = BootstrapSettings(
                    data_root=Path.cwd(), trusted_origins=("http://localhost",),
                )
                with patch("plm_assistant.entrypoints.production_login.read_database_url",
                           return_value=url), patch(
                           "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                           return_value=SimpleNamespace(guard=guard)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                           return_value=SecretListCursorCodec(b"q" * 32)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                           return_value=MemberListCursorCodec(b"m" * 32)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                           return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_document_list_cursor_codec",
                           return_value=DocumentListCursorCodec(b"l" * 32)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_document_version_cursor_codec",
                           return_value=VersionListCursorCodec(b"v" * 32)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_document_parse_cursor_codec",
                           return_value=ParseListCursorCodec(b"p" * 32)):
                    production = create_production_platform_app(settings)
                    with TestClient(production, base_url="http://localhost") as client:
                        prod_headers = {
                            "origin": "http://localhost",
                            "cookie": "plm_session=" + ADMIN_TOKEN.hex(),
                            "x-csrf-token": CSRF.hex(),
                            "idempotency-key": str(uuid.uuid4()),
                        }
                        prod_body = {
                            "code": "P9", "name": "Production Composition Synthetic",
                            "initial_manager_user_id": str(production_manager_id),
                        }
                        first = client.post("/api/v1/projects", headers=prod_headers,
                                            json=prod_body)
                        replay = client.post("/api/v1/projects", headers=prod_headers,
                                             json=prod_body)
                        assert first.status_code == replay.status_code == 201, (first.text, replay.text)
                        assert first.json()["data"] == replay.json()["data"]
                        production_project_id = uuid.UUID(first.json()["data"]["project_id"])
                        forbidden = client.post("/api/v1/projects", headers={
                            **prod_headers, "cookie": "plm_session=" + NONADMIN_TOKEN.hex(),
                            "idempotency-key": str(uuid.uuid4()),
                        }, json={**prod_body, "code": "P10"})
                        assert forbidden.status_code == 404
                        guard.enabled = False
                        denied_prod = client.post("/api/v1/projects", headers={
                            **prod_headers, "idempotency-key": str(uuid.uuid4()),
                        }, json={**prod_body, "code": "P10"})
                        assert denied_prod.status_code == 403
                        guard.enabled = True
                with connect(name) as db:
                    assert db.execute(
                        "SELECT count(*) FROM plm.prj_projects WHERE project_code_normalized='p9'"
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_CREATED'",
                        (production_project_id,),
                    ).fetchone()[0] == 1
                    project_count = db.execute("SELECT count(*) FROM plm.prj_projects").fetchone()[0]
                    assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == project_count
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == project_count
                    assert db.execute("SELECT count(*) FROM plm.wfl_stages").fetchone()[0] == project_count*6
                    assert db.execute("SELECT count(*) FROM plm.wfl_checklist_items WHERE item_state='PENDING'").fetchone()[0] == project_count*12
                    assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows WHERE workflow_state<>'NOT_STARTED' OR current_stage_key IS NOT NULL").fetchone()[0] == 0
                class FailAfterBootstrap:
                    def initialize_in_transaction(self, transaction, **values):
                        kwargs["workflow_initializer"].initialize_in_transaction(transaction, **values)
                        raise RuntimeError("synthetic initializer failure")
                with connect(name) as db:
                    before_counts = tuple(db.execute(f"SELECT count(*) FROM plm.{table}").fetchone()[0] for table in (
                        "prj_projects", "prj_departments", "prj_project_members", "wfl_project_workflows", "aud_events", "plt_idempotency_receipts",
                    ))
                bad_initializer = ProjectCreateService(
                    **(kwargs | {"workflow_initializer": FailAfterBootstrap()}),
                    audit=AuditService(SqlAlchemyAuditRepository()), receipts=receipts,
                )
                failure_command = cmd("P11", manager=initializer_failure_manager)
                failure_key = str(uuid.uuid4())
                try:
                    bad_initializer.create_idempotent(failure_command, idempotency_key=failure_key)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic initializer failure"
                else:
                    raise AssertionError("failed initializer committed Project")
                with connect(name) as db:
                    after_counts = tuple(db.execute(f"SELECT count(*) FROM plm.{table}").fetchone()[0] for table in (
                        "prj_projects", "prj_departments", "prj_project_members", "wfl_project_workflows", "aud_events", "plt_idempotency_receipts",
                    ))
                    assert before_counts == after_counts
                recovered_initializer = idempotent.create_idempotent(failure_command, idempotency_key=failure_key)
                with connect(name) as db:
                    assert db.execute("SELECT workflow_state FROM plm.wfl_project_workflows WHERE project_id=%s", (recovered_initializer.project_id,)).fetchone()[0] == "NOT_STARTED"
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s", (recovered_initializer.project_id,)).fetchone()[0] == 2
                print("PASS: admin/CSRF/License, atomic Project+Workflow bootstrap, concurrent/optional/Windows platform HTTP replay, Audit/initializer rollback and same-key recovery")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
