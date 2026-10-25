"""Windows 11/PostgreSQL 18 proof for Handover Action START."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.handover.application.start_action import (
    HandoverActionStartError, HandoverActionStartService, StartHandoverAction,
)
from plm_assistant.modules.handover.infrastructure.action_start_repository import SqlAlchemyHandoverActionStartRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_start_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def expect(code, action):
    try:
        action()
    except HandoverActionStartError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    name = "hnd02a03a04_" + uuid.uuid4().hex[:8]
    pm_token, owner_token, other_token = b"p" * 32, b"o" * 32, b"x" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=name)
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "Start PM", "NONE", pm_token)
                    owner = seed_user(db, "Start Owner", "NONE", owner_token)
                    other = seed_user(db, "Start Other", "NONE", other_token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDSTA','hndsta','Start Action',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"), (owner, "CUSTOMER_MEMBER"), (other, "CUSTOMER_MEMBER")):
                        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (project, user, department, role))

                    def seed_action(title):
                        action, event, trace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                        reason = "Manual meeting action"
                        with db.transaction():
                            db.execute("INSERT INTO plm.hnd_action_items(action_item_id,project_id,source_kind,human_source_reason,action_type,title,requested_input_spec,owner_ref,due_at,priority,created_by,created_reason) VALUES (%s,%s,'HUMAN','Meeting','OTHER',%s,'{\"fields\":[{\"name\":\"answer\",\"format\":\"text\",\"example\":\"Yes\",\"required\":true}]}'::jsonb,%s,statement_timestamp()+interval '7 days','LOW',%s,%s)", (action, project, title, owner, pm, reason))
                            created = db.execute("SELECT created_at FROM plm.hnd_action_items WHERE action_item_id=%s", (action,)).fetchone()[0]
                            db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,0,NULL,'OPEN',%s,%s,%s,%s)", (event, action, project, pm, reason, created, trace))
                        return action

                    owner_action = seed_action("Owner action")
                    manager_action = seed_action("Manager action")
                    rollback_action = seed_action("Rollback action")
                    concurrent_action = seed_action("Concurrent action")

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                common = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(),
                    license_guard=guard,
                    authorization=authorization,
                    repository=SqlAlchemyHandoverActionStartRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def service(audit=None, license_guard=None):
                    values = dict(common)
                    if audit is not None:
                        values["audit"] = audit
                    if license_guard is not None:
                        values["license_guard"] = license_guard
                    return HandoverActionStartService(**values)

                def start(token, action, expected, key, reason="Work started"):
                    return service().start(StartHandoverAction(
                        token, CSRF, uuid.uuid4(), project, action, expected,
                        reason, key,
                    ))

                first = start(owner_token, owner_action, 0, "owner-start-0001")
                assert first.action_state == "IN_PROGRESS" and first.etag == '"v1"'
                replay = start(owner_token, owner_action, 0, "owner-start-0001")
                assert replay == first
                expect("CONFLICT_IDEMPOTENCY", lambda: start(
                    owner_token, owner_action, 0, "owner-start-0001", "Changed reason",
                ))
                expect("RESOURCE_NOT_FOUND", lambda: start(
                    other_token, manager_action, 0, "other-start-0001",
                ))
                manager = start(pm_token, manager_action, 0, "manager-start-0001")
                assert manager.etag == '"v1"'
                expect("CONFLICT_VERSION", lambda: start(
                    pm_token, rollback_action, 1, "stale-start-0001",
                ))
                expect("HANDOVER_STATE_INVALID", lambda: start(
                    owner_token, owner_action, 1, "second-start-0001",
                ))

                failed = StartHandoverAction(
                    owner_token, CSRF, uuid.uuid4(), project, rollback_action, 0,
                    "Rollback then recover", "rollback-start-0001",
                )
                expect("HANDOVER_UNAVAILABLE", lambda: service(
                    audit=FailedAudit(),
                ).start(failed))
                recovered = service().start(failed)
                assert recovered.etag == '"v1"'

                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(
                    license_guard=expired,
                ).start(replace(
                    failed, action_item_id=uuid.uuid4(),
                    idempotency_key="denied-start-0001",
                )))

                concurrent = StartHandoverAction(
                    owner_token, CSRF, uuid.uuid4(), project, concurrent_action, 0,
                    "Concurrent start", "concurrent-start-0001",
                )
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: service().start(concurrent), range(2)))
                assert results[0] == results[1]

                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_state_events WHERE to_state='IN_PROGRESS'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_STARTED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_HND_ACTION_START' AND state='COMPLETED'").fetchone()[0] == 4
                    states = db.execute("SELECT action_state,lock_version FROM plm.hnd_action_items ORDER BY title").fetchall()
                    assert states == [("IN_PROGRESS", 1)] * 4, states
                print("HND_02_A03_A04_ACTION_START_PASS: owner/manager authorization, OPEN-to-IN_PROGRESS history, strong ETag, idempotency replay/conflict/concurrency, rollback recovery and License denial verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
