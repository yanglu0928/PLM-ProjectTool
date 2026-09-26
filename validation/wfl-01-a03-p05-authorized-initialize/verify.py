"""Disposable real Session/Project proofs; License remains a synthetic guard."""
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from contextlib import ExitStack
from unittest.mock import patch

import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.workflow.api.read_workflow import create_workflow_read_router
from plm_assistant.entrypoints.production_login import (
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app, ProductionLoginStartupError,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.workflow.application.read_workflow import WorkflowReadService, WorkflowReadQuery, WorkflowReadError
from plm_assistant.modules.workflow.infrastructure.read_repository import SqlAlchemyWorkflowReadRepository
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService, ProjectAuthorizationError
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.workflow.application.initialize import WorkflowInitializationService
from plm_assistant.modules.workflow.application.initialize_existing import (
    ExistingWorkflowInitializationService, InitializeExistingWorkflow, WorkflowInitializationError,
)
from plm_assistant.modules.workflow.infrastructure.initialize_repository import SqlAlchemyWorkflowInitializationRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


CSRF = b"c"*32


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=55432, user="poc_admin", dbname=name, autocommit=True)


def user(db, label, token, deployment_role="NONE"):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES(%s,%s,%s) RETURNING user_id", (label, label.lower(), deployment_role)).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES(%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential, uid))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES(%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


class Guard:
    enabled = True
    def require_valid(self, **_kwargs):
        if not self.enabled: raise RuntimeLicenseError("EXPIRED")


class FailedAudit:
    def append(self, *_args): raise RuntimeError("synthetic audit failure")


def main():
    name = "wflpm_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            tokens = [bytes([i])*32 for i in range(1, 7)]
            with connect(name) as db:
                pm, im, customer, pm2, outsider, customer_member = [user(db, label, token, "DEPLOYMENT_ADMIN" if i==4 else "NONE") for i, (label, token) in enumerate(zip(("Manager One", "Implementer", "Customer", "Manager Two", "Global Admin", "Customer Member"), tokens))]
                projects, departments = [], []
                for i in range(2):
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES(%s,%s,%s,%s) RETURNING project_id", (f"WPM{i}", f"wpm{i}", f"Workflow PM {i}", outsider)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES(%s,'D','d','Department') RETURNING department_id", (project,)).fetchone()[0]
                    projects.append(project); departments.append(department)
                for uid, role, index in ((pm,"PROJECT_MANAGER",0), (im,"IMPLEMENTATION_MEMBER",0), (customer,"CUSTOMER_MANAGER",0), (pm2,"PROJECT_MANAGER",1), (customer_member,"CUSTOMER_MEMBER",0)):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES(%s,%s,%s,%s)", (projects[index], uid, departments[index], role))
            guard = Guard()
            bootstrap = WorkflowInitializationService(repository=SqlAlchemyWorkflowInitializationRepository(), audit=AuditService(SqlAlchemyAuditRepository()))
            dependencies = dict(unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectWriteAccess(), projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository()), license_guard=guard)
            service = ExistingWorkflowInitializationService(**dependencies, initializer=bootstrap)
            reads = WorkflowReadService(unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectReadAccess(), projects=dependencies["projects"], license_guard=guard, repository=SqlAlchemyWorkflowReadRepository())
            http_sessions = SessionService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemySessionRepository(), issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()), audit=AuditService(SqlAlchemyAuditRepository()))
            app = create_app(workflow_read_router=create_workflow_read_router(sessions=http_sessions, workflows=reads, origins=LoginOriginPolicy(["http://localhost"])))
            def cookie(index=0): return {"cookie": "plm_session="+tokens[index].hex()}
            path = f"/api/v1/projects/{projects[0]}/workflow"
            def read_request(index=0, project=None):
                return WorkflowReadQuery(tokens[index], project or projects[0], uuid.uuid4())
            def read_denied(query, code):
                try: reads.get(query)
                except WorkflowReadError as exc: assert exc.code == code, (exc.code, code)
                else: raise AssertionError("invalid Workflow read accepted")
            read_denied(read_request(), "RESOURCE_NOT_FOUND")
            def request(index=0, project=None, csrf=CSRF):
                return InitializeExistingWorkflow(tokens[index], csrf, project or projects[0], uuid.uuid4())
            def deny(command_value, code):
                try: service.initialize(command_value)
                except (WorkflowInitializationError, ProjectAuthorizationError) as exc: assert exc.code == code
                else: raise AssertionError("unauthorized Workflow initialization accepted")
            for index in (1,2,3,4,5): deny(request(index), "RESOURCE_NOT_FOUND")
            deny(request(csrf=b"x"*32), "AUTH_ACCESS_DENIED")
            deny(request(project=projects[1]), "RESOURCE_NOT_FOUND")
            guard.enabled = False
            try: service.initialize(request())
            except RuntimeLicenseError: pass
            else: raise AssertionError("expired License accepted")
            guard.enabled = True
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 0
            with ThreadPoolExecutor(max_workers=2) as pool:
                ids = list(pool.map(lambda _i: service.initialize(request()), range(2)))
            assert ids[0] == ids[1] == service.initialize(request())
            for index in (0,1,2,5):
                view = reads.get(read_request(index))
                assert view.workflow_id == ids[0] and view.etag == '"v0"'
                assert len(view.stages) == 6 and sum(len(stage.checklist_items) for stage in view.stages) == 12
            for index in (3,4): read_denied(read_request(index), "RESOURCE_NOT_FOUND")
            read_denied(read_request(project=projects[1]), "RESOURCE_NOT_FOUND")
            read_denied(read_request(3, projects[1]), "RESOURCE_NOT_FOUND")
            guard.enabled = False
            read_denied(read_request(), "LICENSE_OPERATION_DENIED")
            guard.enabled = True
            entered, release = Event(), Event()
            with TestClient(app, base_url="http://localhost") as client:
                for index in (0,1,2,5):
                    response = client.get(path, headers=cookie(index))
                    assert response.status_code == 200, response.text
                    assert response.headers["etag"] == '"v0"' and response.headers["cache-control"] == "no-store"
                    assert response.json()["data"]["workflow_id"] == str(ids[0])
                    assert len(response.json()["data"]["stages"]) == 6
                    assert "definition_fingerprint" not in response.text and "project_id" not in response.json()["data"]
                for index in (3,4): assert client.get(path, headers=cookie(index)).status_code == 404
                assert client.get(f"/api/v1/projects/{projects[1]}/workflow", headers=cookie(3)).status_code == 404
                assert client.get(path).status_code == 401
                assert client.get(path+"?extra=1", headers=cookie()).status_code == 400
                assert client.get(path, headers=cookie() | {"host":"evil.invalid"}).status_code == 403
                guard.enabled = False
                assert client.get(path, headers=cookie()).status_code == 403
                guard.enabled = True
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 1
            with TemporaryDirectory(prefix="plm-wfl-get-") as temporary_root, ExitStack() as patches:
                settings = BootstrapSettings(data_root=Path(temporary_root), trusted_origins=("http://localhost",))
                prefix = "plm_assistant.entrypoints.production_login."
                patches.enter_context(patch(prefix+"read_database_url", return_value=url))
                patches.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services", return_value=SimpleNamespace(guard=guard)))
                for function, codec in (
                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q"*32)),
                    ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m"*32)),
                    ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d"*32)),
                    ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l"*32)),
                    ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v"*32)),
                    ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p"*32)),
                ):
                    patches.enter_context(patch(prefix+function, return_value=codec))
                patches.enter_context(patch("plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service", return_value=object()))
                patches.enter_context(patch(prefix+"create_windows_document_upload_token_issuer", return_value=HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda _ref: b"u"*32), key_ref="document-upload-token-v1")))
                for closed in (create_app(), create_production_login_app(settings)):
                    with TestClient(closed, base_url="http://localhost") as client:
                        assert client.get(path, headers=cookie()).status_code == 404
                for factory in (create_production_platform_app, create_production_platform_write_app):
                    with TestClient(factory(settings), base_url="http://localhost") as client:
                        for index in (0,1,2,5):
                            result = client.get(path, headers=cookie(index))
                            assert result.status_code == 200, result.text
                            assert result.headers["etag"] == '"v0"'
                            assert result.json()["data"]["workflow_id"] == str(ids[0])
                        assert client.get(path, headers=cookie(4)).status_code == 404
                        assert client.get(f"/api/v1/projects/{projects[1]}/workflow", headers=cookie()).status_code == 404
                        guard.enabled = False
                        assert client.get(path, headers=cookie()).status_code == 403
                        guard.enabled = True
                        assert client.post(path+":start", headers=cookie()).status_code == 404
                        assert client.post(path+":transition", headers=cookie()).status_code == 404
                    for missing in ("license", "cursor"):
                        target = "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services" if missing == "license" else prefix+"create_windows_secret_list_cursor_codec"
                        with patch(target, side_effect=RuntimeError("synthetic missing trust")):
                            try: factory(settings)
                            except ProductionLoginStartupError: pass
                            else: raise AssertionError("platform opened without required trust source")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 1
            class WaitingRepository:
                def get(self, tx, project):
                    entered.set()
                    assert release.wait(timeout=10)
                    return SqlAlchemyWorkflowReadRepository().get(tx, project)
            locked_reads = WorkflowReadService(unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectReadAccess(), projects=dependencies["projects"], license_guard=guard, repository=WaitingRepository())
            with ThreadPoolExecutor(max_workers=1) as pool:
                waiting = pool.submit(locked_reads.get, read_request())
                try:
                    assert entered.wait(timeout=10)
                    with connect(name) as db:
                        db.execute("SET lock_timeout='150ms'")
                        try:
                            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s", (pm,))
                        except psycopg.errors.LockNotAvailable:
                            pass
                        else:
                            raise AssertionError("member revocation raced authorized Workflow read")
                finally:
                    release.set()
                assert waiting.result(timeout=10).workflow_id == ids[0]
            failing = ExistingWorkflowInitializationService(**dependencies, initializer=WorkflowInitializationService(repository=SqlAlchemyWorkflowInitializationRepository(), audit=FailedAudit()))
            try: failing.initialize(request(3, projects[1]))
            except RuntimeError as exc: assert "synthetic audit failure" in str(exc)
            else: raise AssertionError("failed audit committed Workflow")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 1
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s", (projects[0],))
            deny(request(), "PROJECT_ARCHIVED")
            assert reads.get(read_request()).state == "NOT_STARTED"
            with TestClient(app, base_url="http://localhost") as client:
                assert client.get(path, headers=cookie()).status_code == 200
            with connect(name) as db:
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='TEST_REVOKED',lock_version=lock_version+1 WHERE user_id=%s", (pm,))
            deny(request(), "AUTH_ACCESS_DENIED")
            read_denied(read_request(), "AUTH_ACCESS_DENIED")
            with TestClient(app, base_url="http://localhost") as client:
                assert client.get(path, headers=cookie()).status_code == 401
            with connect(name) as db:
                assert db.execute("SELECT workflow_state,current_stage_key FROM plm.wfl_project_workflows WHERE workflow_id=%s", (ids[0],)).fetchone() == ("NOT_STARTED", None)
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_items WHERE item_state='PENDING'").fetchone()[0] == 12
            print("PASS: real Session/CSRF/project PM, cross-project/non-PM/admin/archived/revoked rejection, synthetic License denial, concurrent dedupe and Audit rollback; not HTTP or Gate")
            print("PASS: Workflow read snapshot, all four project roles, archived read, missing instance no initialization, cross-project/admin/session/License rejection; not HTTP")
            print("PASS: opt-in Workflow GET real Session/PostgreSQL HTTP, safe projection/ETag/no-store, four roles/archived and errors; synthetic License, not production composition/Gate")
            print("PASS: both Windows explicit platform compositions Workflow GET, default/login and write routes closed, missing synthetic trust fail-closed; formal trust/Gate not verified")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__": main()
