"""Windows 11/PostgreSQL 18 proof for Handover Action SUBMIT."""

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
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.handover.application.source_validation import (
    HandoverDocumentRef, HandoverSourceValidator,
)
from plm_assistant.modules.handover.application.submit_action import (
    HandoverActionSubmitError, HandoverActionSubmitService,
    SubmitHandoverAction,
)
from plm_assistant.modules.handover.infrastructure.action_submit_repository import SqlAlchemyHandoverActionSubmitRepository
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


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_submit_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def expect(code, action):
    try:
        action()
    except HandoverActionSubmitError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    name = "hnd02a03a05_" + uuid.uuid4().hex[:8]
    pm_token, owner_token = b"p" * 32, b"o" * 32
    im_token, other_token = b"i" * 32, b"x" * 32
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
                    pm = seed_user(db, "Submit PM", "NONE", pm_token)
                    owner = seed_user(db, "Submit Owner", "NONE", owner_token)
                    implementer = seed_user(db, "Submit IM", "NONE", im_token)
                    other = seed_user(db, "Submit Other", "NONE", other_token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDSUB','hndsub','Submit Action',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"), (owner, "CUSTOMER_MEMBER"), (implementer, "IMPLEMENTATION_MEMBER"), (other, "CUSTOMER_MEMBER")):
                        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (project, user, department, role))
                    source = p01.seed_project_document(db, pm, project, "action-response")
                    other_source = p01.seed_project_document(db, pm, project, "unreferenced-response")
                    evidence, unrelated_evidence = uuid.uuid4(), uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for evidence_id, ref, label in ((evidence, source, "Submission evidence"), (unrelated_evidence, other_source, "Unrelated evidence")):
                            db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,%s,'ELIGIBLE','fixture',%s)", (evidence_id, project, ref.document_id, ref.document_version_id, b'e' * 32, label, pm))

                    def seed_action(title):
                        action, created_event, start_event = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                        trace, reason = uuid.uuid4(), "Manual meeting action"
                        with db.transaction():
                            db.execute("INSERT INTO plm.hnd_action_items(action_item_id,project_id,source_kind,human_source_reason,action_type,title,requested_input_spec,owner_ref,due_at,priority,created_by,created_reason) VALUES (%s,%s,'HUMAN','Meeting','OTHER',%s,'{\"fields\":[{\"name\":\"answer\",\"format\":\"text\",\"example\":\"Yes\",\"required\":true}]}'::jsonb,%s,statement_timestamp()+interval '7 days','LOW',%s,%s)", (action, project, title, owner, pm, reason))
                            created = db.execute("SELECT created_at FROM plm.hnd_action_items WHERE action_item_id=%s", (action,)).fetchone()[0]
                            db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,0,NULL,'OPEN',%s,%s,%s,%s)", (created_event, action, project, pm, reason, created, trace))
                            db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,1,'OPEN','IN_PROGRESS',%s,'Work started',%s,%s)", (start_event, action, project, owner, created, uuid.uuid4()))
                            db.execute("UPDATE plm.hnd_action_items SET action_state='IN_PROGRESS',updated_by=%s,updated_at=%s,lock_version=1 WHERE action_item_id=%s", (owner, created, action))
                        return action

                    owner_action = seed_action("Owner submit")
                    im_action = seed_action("Implementer submit")
                    manager_denied_action = seed_action("Manager denied")
                    source_action = seed_action("Invalid source")
                    evidence_action = seed_action("Invalid evidence")
                    rollback_action = seed_action("Rollback submit")
                    concurrent_action = seed_action("Concurrent submit")

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
                    sources=HandoverSourceValidator(SqlAlchemyDocumentReadRepository()),
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    repository=SqlAlchemyHandoverActionSubmitRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def service(audit=None, license_guard=None):
                    values = dict(common)
                    if audit is not None:
                        values["audit"] = audit
                    if license_guard is not None:
                        values["license_guard"] = license_guard
                    return HandoverActionSubmitService(**values)

                def submit(token, action, expected, key, documents=(source,), evidence_refs=(evidence,), reason="Response submitted"):
                    return service().submit(SubmitHandoverAction(
                        token, CSRF, uuid.uuid4(), project, action, expected,
                        documents, evidence_refs, reason, key,
                    ))

                first = submit(owner_token, owner_action, 1, "owner-submit-0001")
                assert first.action_state == "SUBMITTED" and first.etag == '"v2"'
                replay = submit(owner_token, owner_action, 1, "owner-submit-0001")
                assert replay == first
                expect("CONFLICT_IDEMPOTENCY", lambda: submit(
                    owner_token, owner_action, 1, "owner-submit-0001",
                    reason="Changed reason",
                ))
                implementer_view = submit(im_token, im_action, 1, "implementer-submit-0001")
                assert implementer_view.etag == '"v2"'
                expect("RESOURCE_NOT_FOUND", lambda: submit(
                    pm_token, manager_denied_action, 1, "manager-submit-0001",
                ))
                expect("HANDOVER_ACTION_STATE_INVALID", lambda: submit(
                    owner_token, owner_action, 2, "repeat-submit-0001",
                ))
                expect("CONFLICT_VERSION", lambda: submit(
                    owner_token, rollback_action, 0, "stale-submit-0001",
                ))
                missing = HandoverDocumentRef(uuid.uuid4(), uuid.uuid4())
                expect("HANDOVER_SOURCE_REQUIRED", lambda: submit(
                    owner_token, source_action, 1, "source-submit-0001",
                    documents=(missing,),
                ))
                expect("HANDOVER_ACTION_EVIDENCE_REQUIRED", lambda: submit(
                    owner_token, evidence_action, 1, "evidence-submit-0001",
                    evidence_refs=(unrelated_evidence,),
                ))

                failed = SubmitHandoverAction(
                    owner_token, CSRF, uuid.uuid4(), project, rollback_action, 1,
                    (source,), (evidence,), "Rollback then recover",
                    "rollback-submit-0001",
                )
                expect("HANDOVER_UNAVAILABLE", lambda: service(
                    audit=FailedAudit(),
                ).submit(failed))
                recovered = service().submit(failed)
                assert recovered.etag == '"v2"'

                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(
                    license_guard=expired,
                ).submit(replace(
                    failed, action_item_id=evidence_action,
                    idempotency_key="denied-submit-0001",
                )))

                concurrent = SubmitHandoverAction(
                    owner_token, CSRF, uuid.uuid4(), project, concurrent_action, 1,
                    (source,), (evidence,), "Concurrent submit",
                    "concurrent-submit-0001",
                )
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: service().submit(concurrent), range(2)))
                assert results[0] == results[1]

                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_items WHERE action_state='SUBMITTED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_response_refs").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_evidence_refs WHERE purpose='SUBMISSION'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_SUBMITTED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_HND_ACTION_SUBMIT' AND state='COMPLETED'").fetchone()[0] == 4
                print("HND_02_A03_A05_ACTION_SUBMIT_PASS: owner/ImplementationMember authorization, fixed response Documents and matching Evidence, IN_PROGRESS-to-SUBMITTED history, idempotency/concurrency, rollback recovery and License denial verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
