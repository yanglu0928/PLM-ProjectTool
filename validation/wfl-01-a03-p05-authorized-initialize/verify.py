"""Disposable real Session/Project proofs; License remains a synthetic guard."""
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
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
            tokens = [bytes([i])*32 for i in range(1, 6)]
            with connect(name) as db:
                pm, im, customer, pm2, outsider = [user(db, label, token, "DEPLOYMENT_ADMIN" if i==4 else "NONE") for i, (label, token) in enumerate(zip(("Manager One", "Implementer", "Customer", "Manager Two", "Global Admin"), tokens))]
                projects, departments = [], []
                for i in range(2):
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES(%s,%s,%s,%s) RETURNING project_id", (f"WPM{i}", f"wpm{i}", f"Workflow PM {i}", outsider)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES(%s,'D','d','Department') RETURNING department_id", (project,)).fetchone()[0]
                    projects.append(project); departments.append(department)
                for uid, role, index in ((pm,"PROJECT_MANAGER",0), (im,"IMPLEMENTATION_MEMBER",0), (customer,"CUSTOMER_MANAGER",0), (pm2,"PROJECT_MANAGER",1)):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES(%s,%s,%s,%s)", (projects[index], uid, departments[index], role))
            guard = Guard()
            bootstrap = WorkflowInitializationService(repository=SqlAlchemyWorkflowInitializationRepository(), audit=AuditService(SqlAlchemyAuditRepository()))
            dependencies = dict(unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectWriteAccess(), projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository()), license_guard=guard)
            service = ExistingWorkflowInitializationService(**dependencies, initializer=bootstrap)
            def request(index=0, project=None, csrf=CSRF):
                return InitializeExistingWorkflow(tokens[index], csrf, project or projects[0], uuid.uuid4())
            def deny(command_value, code):
                try: service.initialize(command_value)
                except (WorkflowInitializationError, ProjectAuthorizationError) as exc: assert exc.code == code
                else: raise AssertionError("unauthorized Workflow initialization accepted")
            for index in (1,2,3,4): deny(request(index), "RESOURCE_NOT_FOUND")
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
            failing = ExistingWorkflowInitializationService(**dependencies, initializer=WorkflowInitializationService(repository=SqlAlchemyWorkflowInitializationRepository(), audit=FailedAudit()))
            try: failing.initialize(request(3, projects[1]))
            except RuntimeError as exc: assert "synthetic audit failure" in str(exc)
            else: raise AssertionError("failed audit committed Workflow")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 1
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s", (projects[0],))
            deny(request(), "PROJECT_ARCHIVED")
            with connect(name) as db:
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='TEST_REVOKED',lock_version=lock_version+1 WHERE user_id=%s", (pm,))
            deny(request(), "AUTH_ACCESS_DENIED")
            with connect(name) as db:
                assert db.execute("SELECT workflow_state,current_stage_key FROM plm.wfl_project_workflows WHERE workflow_id=%s", (ids[0],)).fetchone() == ("NOT_STARTED", None)
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_items WHERE item_state='PENDING'").fetchone()[0] == 12
            print("PASS: real Session/CSRF/project PM, cross-project/non-PM/admin/archived/revoked rejection, synthetic License denial, concurrent dedupe and Audit rollback; not HTTP or Gate")
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__": main()
