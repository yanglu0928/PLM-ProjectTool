"""Real PostgreSQL proof for authorized, audited, idempotent Workflow start."""

from __future__ import annotations

import argparse
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.workflow.application.start_workflow import (
    StartWorkflow, WorkflowStartError, WorkflowStartService,
)
from plm_assistant.modules.workflow.infrastructure.read_repository import SqlAlchemyWorkflowReadRepository
from plm_assistant.modules.workflow.infrastructure.start_repository import SqlAlchemyWorkflowStartRepository


SOURCE = Path(__file__).resolve().parents[1] / "wfl-01-a06-p01-start-repository" / "verify.py"
spec = spec_from_file_location("_workflow_start_cluster", SOURCE)
cluster = module_from_spec(spec)
spec.loader.exec_module(cluster)
fixture = cluster.fixture
CSRF = b"c" * 32


def _user(db, label: str, token: bytes) -> uuid.UUID:
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES(%s,%s) RETURNING user_id", (label, label.lower()),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
        "password_hash,algorithm_id,parameter_set) "
        "VALUES(%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (user_id,),
    ).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,"
               "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
               (credential, user_id))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,"
               "user_id,credential_version,idle_expires_at,absolute_expires_at) "
               "VALUES(%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
               "statement_timestamp()+interval '1 hour')",
               (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id))
    return user_id


class Guard:
    enabled = True

    def require_valid(self, **_kwargs):
        if not self.enabled:
            from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
            raise RuntimeLicenseError("EXPIRED")


class FailingAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


def _matrix() -> None:
    name = "wflservice_" + uuid.uuid4().hex[:12]
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                             host="127.0.0.1", port=cluster.PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            runtime = create_database_runtime(url)
            tokens = (b"s" * 32, b"t" * 32, b"u" * 32,
                      b"m" * 32, b"o" * 32)
            with fixture.connect(name) as db:
                managers = [_user(db, f"Workflow Manager {index}", tokens[index])
                            for index in range(3)]
                member = _user(db, "Workflow Member", tokens[3])
                outsider = _user(db, "Workflow Outsider", tokens[4])
                projects = []
                with db.transaction():
                    for index in range(3):
                        project = fixture.insert(db, "prj_projects", dict(
                            project_code=f"WSERVICE{index}",
                            project_code_normalized=f"wservice{index}",
                            name=f"Synthetic workflow service {index}",
                            created_by=managers[index]), "project_id")
                        department = fixture.insert(db, "prj_departments", dict(
                            project_id=project, department_code="D",
                            department_code_normalized="d", name="Department"),
                            "department_id")
                        fixture.insert(db, "prj_project_members", dict(
                            project_id=project, user_id=managers[index], department_id=department,
                            project_role="PROJECT_MANAGER"), "project_member_id")
                        if index == 0:
                            fixture.insert(db, "prj_project_members", dict(
                                project_id=project, user_id=member,
                                department_id=department,
                                project_role="IMPLEMENTATION_MEMBER"),
                                "project_member_id")
                        fixture.initialize(db, project, managers[index])
                        projects.append(project)

            guard = Guard()
            reader = SqlAlchemyWorkflowReadRepository()
            base = dict(
                unit_of_work=runtime.unit_of_work,
                sessions=SqlAlchemyProjectWriteAccess(),
                projects=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository()),
                license_guard=guard,
                starter=SqlAlchemyWorkflowStartRepository(reader=reader),
                reader=reader,
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            service = WorkflowStartService(
                **base, audit=AuditService(SqlAlchemyAuditRepository()))

            def start_command(index=0, token=None, csrf=CSRF, version=0):
                return StartWorkflow(token if token is not None else tokens[index],
                                     csrf, projects[index], uuid.uuid4(), version)

            def denied(candidate, code, key="workflow-start-key-1234", target=service):
                try:
                    target.start(candidate, idempotency_key=key)
                except WorkflowStartError as error:
                    assert error.code == code, (error.code, code)
                else:
                    raise AssertionError(f"Workflow start unexpectedly accepted: {code}")

            denied(start_command(token=tokens[3]), "RESOURCE_NOT_FOUND")
            denied(start_command(token=tokens[4]), "RESOURCE_NOT_FOUND")
            denied(start_command(csrf=b"x" * 32), "AUTH_ACCESS_DENIED")
            guard.enabled = False
            denied(start_command(), "LICENSE_OPERATION_DENIED")
            guard.enabled = True
            denied(start_command(version=1), "CONFLICT_VERSION")
            with fixture.connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='WORKFLOW_STARTED'").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                  "WHERE operation='V1_WORKFLOW_START'").fetchone()[0] == 0

            key = "workflow-start-key-1234"
            first = service.start(start_command(), idempotency_key=key)
            assert first.state == "ACTIVE" and first.current_stage == "HANDOVER"
            assert first.etag == '"v1"' and first.project_id == projects[0]
            replay = service.start(start_command(), idempotency_key=key)
            assert replay == first
            denied(start_command(version=1), "CONFLICT_IDEMPOTENCY", key)
            denied(start_command(), "CONFLICT_VERSION", "workflow-another-key-1")
            denied(start_command(version=1), "CONFLICT_STATE", "workflow-another-key-2")
            with fixture.connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='WORKFLOW_STARTED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                  "WHERE operation='V1_WORKFLOW_START' AND state='COMPLETED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_records").fetchone()[0] == 0

            failing = WorkflowStartService(**base, audit=FailingAudit())
            denied(start_command(1), "WORKFLOW_UNAVAILABLE", target=failing)
            with runtime.unit_of_work() as tx:
                assert reader.get(tx, projects[1]).state == "NOT_STARTED"
            with fixture.connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                  "WHERE project_id=%s", (projects[1],)).fetchone()[0] == 0

            def competing(_):
                return service.start(start_command(2),
                                     idempotency_key="workflow-concurrent-123").workflow_id

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(competing, (0, 1)))
            assert outcomes[0] == outcomes[1]
            with fixture.connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='WORKFLOW_STARTED' AND target_project_id=%s",
                                  (projects[2],)).fetchone()[0] == 1
            print("Workflow start service PASS: real PG18/Session/CSRF/PM/License-deny/"
                  "initial/replay/conflict/Audit rollback/concurrency; no Gate or public API",
                  flush=True)
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    options = parser.parse_args()
    cluster._matrix = _matrix
    cluster.verify(options.pg_bin, options.temp_root)
