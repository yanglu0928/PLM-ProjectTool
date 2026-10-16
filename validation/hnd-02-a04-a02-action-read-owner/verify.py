"""Windows 11/PostgreSQL 18 proof for Handover Action LIST/GET Owner."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.handover.application.read_actions import (
    HandoverActionReadError, HandoverActionReadQuery, HandoverActionReadService,
)
from plm_assistant.modules.handover.infrastructure.action_read_repository import SqlAlchemyHandoverActionReadRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
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


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_read_fixture")
connect, seed_user = p01.connect, p01.seed_user
Guard = p01.Guard


def expect(code, action):
    try:
        action()
    except HandoverActionReadError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    name = "hnd02a04a02_" + uuid.uuid4().hex[:8]
    tokens = [bytes([value]) * 32 for value in (112, 105, 109, 99, 102)]
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
                    users = [seed_user(db, "Read " + role, "NONE", token) for role, token in zip(("PM", "IM", "CM", "CUSTOMER", "FOREIGN"), tokens)]
                    pm, implementer, customer_manager, customer, foreign = users
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDREAD','hndread','Read Action',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    foreign_project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDFOREIGN','hndforeign','Foreign',%s) RETURNING project_id", (foreign,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    foreign_department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Foreign') RETURNING department_id", (foreign_project,)).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"), (implementer, "IMPLEMENTATION_MEMBER"), (customer_manager, "CUSTOMER_MANAGER"), (customer, "CUSTOMER_MEMBER")):
                        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (project, user, department, role))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (foreign_project, foreign, foreign_department))
                    document = p01.seed_project_document(db, pm, project, "read-response")
                    evidence = uuid.uuid4()
                    fixed = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Read evidence','ELIGIBLE','fixture',%s)", (evidence, project, document.document_id, document.document_version_id, b'e' * 32, pm))

                    def seed_action(title, state="OPEN", target_project=project, actor=pm):
                        action = uuid.uuid4()
                        version = 2 if state == "SUBMITTED" else 0
                        with db.transaction():
                            db.execute("SET LOCAL session_replication_role='replica'")
                            db.execute("INSERT INTO plm.hnd_action_items(action_item_id,project_id,source_kind,human_source_reason,action_type,title,requested_input_spec,owner_ref,due_at,priority,action_state,submitted_at,created_by,created_reason,created_at,updated_by,updated_at,lock_version) VALUES (%s,%s,'HUMAN','Meeting','PROVIDE_INFO',%s,'{\"fields\":[{\"name\":\"answer\",\"required\":true}]}'::jsonb,%s,%s + interval '7 days','HIGH',%s,CASE WHEN %s=2 THEN %s END,%s,'Read fixture',%s,CASE WHEN %s>0 THEN %s END,%s,%s)", (action, target_project, title, actor, fixed, state, version, fixed, actor, fixed, version, actor, fixed, version))
                            transitions = [(None, "OPEN"), ("OPEN", "IN_PROGRESS"), ("IN_PROGRESS", "SUBMITTED")]
                            for sequence, (before, after) in enumerate(transitions[:version + 1]):
                                reason = "Read fixture" if sequence == 0 else "Read transition"
                                db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (uuid.uuid4(), action, target_project, sequence, before, after, actor, reason, fixed, uuid.uuid4()))
                            if version == 2:
                                db.execute("INSERT INTO plm.hnd_action_response_refs(action_response_ref_id,action_item_id,project_id,document_id,document_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,0)", (uuid.uuid4(), action, target_project, document.document_id, document.document_version_id))
                                db.execute("INSERT INTO plm.hnd_action_evidence_refs(action_evidence_ref_id,action_item_id,project_id,evidence_id,purpose,ordinal) VALUES (%s,%s,%s,%s,'SUBMISSION',0)", (uuid.uuid4(), action, target_project, evidence))
                        return action

                    first = seed_action("First")
                    second = seed_action("Second")
                    submitted = seed_action("Submitted", "SUBMITTED")
                    foreign_action = seed_action("Foreign", target_project=foreign_project, actor=foreign)
                    before = db.execute("SELECT (SELECT count(*) FROM plm.aud_events),(SELECT count(*) FROM plm.plt_idempotency_receipts),(SELECT count(*) FROM plm.hnd_action_state_events)").fetchone()

                guard = Guard()
                authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
                def service(custom_guard=None):
                    return HandoverActionReadService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyProjectReadAccess(),
                        license_guard=custom_guard or guard,
                        authorization=authorization,
                        repository=SqlAlchemyHandoverActionReadRepository(),
                    )
                def query(index, selected_project=project):
                    return HandoverActionReadQuery(tokens[index], uuid.uuid4(), selected_project)

                for index in range(4):
                    page = service().list_page(query(index), page_size=2)
                    assert len(page.items) == 2 and page.has_more
                    tail = service().list_page(query(index), page_size=2, after_updated_at=page.next_updated_at, after_action_item_id=page.next_action_item_id)
                    assert len(tail.items) == 1 and not tail.has_more
                    assert len({item.action_item_id for item in page.items + tail.items}) == 3
                detail = service().get(query(0), submitted)
                assert detail.summary.action_state == "SUBMITTED" and detail.summary.etag == '"v2"'
                assert len(detail.responses) == 1 and len(detail.evidence) == 1
                assert detail.current_event.sequence_no == 2 and detail.current_event.to_state == "SUBMITTED"
                expect("RESOURCE_NOT_FOUND", lambda: service().get(query(0), foreign_action))
                expect("RESOURCE_NOT_FOUND", lambda: service().list_page(query(4), page_size=10))
                expect("RESOURCE_NOT_FOUND", lambda: service().get(query(0), uuid.uuid4()))

                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
                assert len(service().list_page(query(0), page_size=10).items) == 3
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s", (project,))
                    db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_id=%s AND user_id=%s", (project, customer))
                expect("RESOURCE_NOT_FOUND", lambda: service().list_page(query(3), page_size=10))
                expired = Guard(); expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(expired).get(query(0), first))

                with connect(name) as db:
                    after = db.execute("SELECT (SELECT count(*) FROM plm.aud_events),(SELECT count(*) FROM plm.plt_idempotency_receipts),(SELECT count(*) FROM plm.hnd_action_state_events)").fetchone()
                    assert before == after, (before, after)
                print("HND_02_A04_A02_ACTION_READ_OWNER_PASS: four-role current membership, stable tied-timestamp pagination, bounded summary, safe detail/current event, cross-project/missing/revoked denial, archived read, License fail-closed and zero writes verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
