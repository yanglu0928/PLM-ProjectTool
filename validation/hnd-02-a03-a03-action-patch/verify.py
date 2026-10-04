"""Windows 11/PostgreSQL 18 proof for Handover Action metadata PATCH."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.handover.application.patch_action import (
    HandoverActionPatchError, HandoverActionPatchService, PatchHandoverAction,
)
from plm_assistant.modules.handover.infrastructure.action_patch_repository import SqlAlchemyHandoverActionPatchRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.handover_action_assignee import SqlAlchemyHandoverActionAssigneeSource


ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_patch_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def expect(code, action):
    try:
        action()
    except HandoverActionPatchError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    name = "hnd02a03a03_" + uuid.uuid4().hex[:8]
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
                    pm = seed_user(db, "Patch PM", "NONE", pm_token)
                    owner = seed_user(db, "Patch Owner", "NONE", owner_token)
                    other = seed_user(db, "Patch Other", "NONE", other_token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDPAT','hndpat','Patch Action',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    for user, role in ((pm,"PROJECT_MANAGER"),(owner,"CUSTOMER_MEMBER"),(other,"CUSTOMER_MEMBER")):
                        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (project,user,department,role))
                    action, event, trace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                    reason = "Manual meeting action"
                    with db.transaction():
                        db.execute("INSERT INTO plm.hnd_action_items(action_item_id,project_id,source_kind,human_source_reason,action_type,title,requested_input_spec,owner_ref,due_at,priority,created_by,created_reason) VALUES (%s,%s,'HUMAN','Meeting','OTHER','Follow up','{\"fields\":[{\"name\":\"answer\",\"format\":\"text\",\"example\":\"Yes\",\"required\":true}]}'::jsonb,%s,statement_timestamp()+interval '7 days','LOW',%s,%s)", (action,project,owner,pm,reason))
                        created = db.execute("SELECT created_at FROM plm.hnd_action_items WHERE action_item_id=%s",(action,)).fetchone()[0]
                        db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,0,NULL,'OPEN',%s,%s,%s,%s)",(event,action,project,pm,reason,created,trace))

                guard = Guard()
                authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
                common = dict(unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(), license_guard=guard, authorization=authorization, assignees=SqlAlchemyHandoverActionAssigneeSource(), repository=SqlAlchemyHandoverActionPatchRepository(), audit=AuditService(SqlAlchemyAuditRepository()))
                def service(audit=None, license_guard=None):
                    values=dict(common)
                    if audit is not None: values["audit"]=audit
                    if license_guard is not None: values["license_guard"]=license_guard
                    return HandoverActionPatchService(**values)
                def patch(token, expected, **changes):
                    return service().patch(PatchHandoverAction(token,CSRF,uuid.uuid4(),project,action,expected,**changes))

                first = patch(owner_token,0,title="Owner updated follow-up")
                assert first.etag=='"v1"'
                same = patch(owner_token,1,title="Owner updated follow-up")
                assert same.etag=='"v1"'
                expect("RESOURCE_NOT_FOUND",lambda:patch(other_token,1,priority="HIGH"))
                expect("CONFLICT_VERSION",lambda:patch(pm_token,0,priority="HIGH"))
                second = patch(pm_token,1,priority="HIGH",due_at=datetime.now(timezone.utc)+timedelta(days=9))
                assert second.etag=='"v2"'

                failed = PatchHandoverAction(pm_token,CSRF,uuid.uuid4(),project,action,2,title="Rolled back")
                expect("HANDOVER_UNAVAILABLE",lambda:service(audit=FailedAudit()).patch(failed))
                recovered = service().patch(failed)
                assert recovered.etag=='"v3"'
                expired=Guard(); expired.enabled=False
                expect("LICENSE_OPERATION_DENIED",lambda:service(license_guard=expired).patch(replace(failed,expected_version=3,title="Denied")))

                with connect(name) as db:
                    row=db.execute("SELECT title,priority,lock_version FROM plm.hnd_action_items WHERE action_item_id=%s",(action,)).fetchone()
                    assert row==("Rolled back","HIGH",3),row
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_state_events WHERE action_item_id=%s",(action,)).fetchone()[0]==4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_PATCHED'").fetchone()[0]==3
                try:
                    command.downgrade(cfg,"20261005_0099")
                except Exception as error:
                    assert "metadata history prevents downgrade" in str(error),str(error)
                else:
                    raise AssertionError("metadata history accepted downgrade")
                print("HND_02_A03_A03_ACTION_PATCH_PASS: assigned owner/manager authorization, partial metadata, strong ETag, no-op, rollback, License denial, same-state history and downgrade refusal verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
