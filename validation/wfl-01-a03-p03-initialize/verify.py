"""Internal transactional initializer, synthetic callers; not permission/UAT proof."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.workflow.application.initialize import WorkflowInitializationService
from plm_assistant.modules.workflow.infrastructure.initialize_repository import SqlAlchemyWorkflowInitializationRepository


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=55432, user="poc_admin", dbname=name, autocommit=True)


class FailingAudit:
    def append(self, *_args):
        raise RuntimeError("synthetic audit failure")


def main():
    name = "wflinit_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            audit = AuditService(SqlAlchemyAuditRepository())
            service = WorkflowInitializationService(repository=SqlAlchemyWorkflowInitializationRepository(), audit=audit)
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES('Init Owner','init owner') RETURNING user_id").fetchone()[0]
                projects = [db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES(%s,%s,%s,%s) RETURNING project_id",
                    (f"INIT{i}", f"init{i}", f"Initialize {i}", actor),
                ).fetchone()[0] for i in range(3)]
            def initialize(project):
                with runtime.unit_of_work() as tx:
                    result = service.initialize_in_transaction(tx, project_id=project, actor_id=actor, trace_id=uuid.uuid4())
                    tx.commit()
                    return result
            first = initialize(projects[0])
            assert initialize(projects[0]) == first
            barrier = Barrier(2)
            def concurrent():
                barrier.wait(timeout=10)
                return initialize(projects[1])
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(concurrent) for _ in range(2)]
                results = [future.result(timeout=30) for future in futures]
            assert results[0] == results[1]
            failing = WorkflowInitializationService(repository=SqlAlchemyWorkflowInitializationRepository(), audit=FailingAudit())
            try:
                with runtime.unit_of_work() as tx:
                    failing.initialize_in_transaction(tx, project_id=projects[2], actor_id=actor, trace_id=uuid.uuid4())
                    tx.commit()
            except RuntimeError as exc:
                assert "synthetic audit failure" in str(exc)
            else:
                raise AssertionError("audit failure accepted")
            # Deferred constraints and caller-side failure both roll back bootstrap.
            try:
                with runtime.unit_of_work() as tx:
                    service.initialize_in_transaction(tx, project_id=projects[2], actor_id=actor, trace_id=uuid.uuid4())
                    tx.session.execute(text("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER',lock_version=1 WHERE project_id=:project"), {"project": projects[2]})
                    tx.commit()
            except Exception as exc:
                assert "Workflow current stage structure invalid" in str(exc)
            else:
                raise AssertionError("deferred invalid state committed")
            with runtime.unit_of_work() as tx:
                service.initialize_in_transaction(tx, project_id=projects[2], actor_id=actor, trace_id=uuid.uuid4())
                # Deliberately omit commit; caller aborts.
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.wfl_stages").fetchone()[0] == 12
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_checklists").fetchone()[0] == 12
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_items").fetchone()[0] == 24
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_items WHERE item_state<>'PENDING'").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows WHERE workflow_state<>'NOT_STARTED' OR current_stage_key IS NOT NULL").fetchone()[0] == 0
                with db.transaction():
                    db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER',lock_version=1 WHERE workflow_id=%s", (first,))
                    db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'", (first,))
            assert initialize(projects[0]) == first
            with connect(name) as db:
                assert db.execute("SELECT workflow_state,current_stage_key,lock_version FROM plm.wfl_project_workflows WHERE workflow_id=%s", (first,)).fetchone() == ("ACTIVE", "HANDOVER", 1)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='WORKFLOW_INITIALIZED'").fetchone()[0] == 2
            print("PASS: internal initialize/retry/concurrent uniqueness, pending facts, one Audit each, Audit/deferred/caller rollback; synthetic caller only")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
