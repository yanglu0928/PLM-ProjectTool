"""Windows 11/PostgreSQL 18 proof for Handover Action VERIFY."""

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
from plm_assistant.modules.handover.application.source_validation import HandoverSourceValidator
from plm_assistant.modules.handover.application.verify_action import (
    HandoverActionVerifyError, HandoverActionVerifyService,
    VerifyHandoverAction,
)
from plm_assistant.modules.handover.infrastructure.action_verify_repository import SqlAlchemyHandoverActionVerifyRepository
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


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_verify_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def expect(code, action):
    try:
        action()
    except HandoverActionVerifyError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    name = "hnd02a03a06_" + uuid.uuid4().hex[:8]
    pm_token, cm_token, im_token, owner_token = b"p" * 32, b"m" * 32, b"i" * 32, b"o" * 32
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
                    pm = seed_user(db, "Verify PM", "NONE", pm_token)
                    manager = seed_user(db, "Verify CM", "NONE", cm_token)
                    implementer = seed_user(db, "Verify IM", "NONE", im_token)
                    owner = seed_user(db, "Verify Owner", "NONE", owner_token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDVER','hndver','Verify Action',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"), (manager, "CUSTOMER_MANAGER"), (implementer, "IMPLEMENTATION_MEMBER"), (owner, "CUSTOMER_MEMBER")):
                        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (project, user, department, role))
                    source = p01.seed_project_document(db, pm, project, "verified-response")
                    unrelated = p01.seed_project_document(db, pm, project, "unrelated-verification")
                    submission_evidence, verification_evidence, unrelated_evidence = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        for evidence_id, ref, label in ((submission_evidence, source, "Submission"), (verification_evidence, source, "Verification"), (unrelated_evidence, unrelated, "Unrelated")):
                            db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,%s,'ELIGIBLE','fixture',%s)", (evidence_id, project, ref.document_id, ref.document_version_id, b'e' * 32, label, pm))

                    def seed_action(title):
                        action = uuid.uuid4()
                        reason, created = "Manual meeting action", None
                        with db.transaction():
                            db.execute("INSERT INTO plm.hnd_action_items(action_item_id,project_id,source_kind,human_source_reason,action_type,title,requested_input_spec,owner_ref,due_at,priority,created_by,created_reason) VALUES (%s,%s,'HUMAN','Meeting','OTHER',%s,'{\"fields\":[{\"name\":\"answer\",\"format\":\"text\",\"example\":\"Yes\",\"required\":true}]}'::jsonb,%s,statement_timestamp()+interval '7 days','LOW',%s,%s)", (action, project, title, owner, pm, reason))
                            created = db.execute("SELECT created_at FROM plm.hnd_action_items WHERE action_item_id=%s", (action,)).fetchone()[0]
                            db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,0,NULL,'OPEN',%s,%s,%s,%s)", (uuid.uuid4(), action, project, pm, reason, created, uuid.uuid4()))
                            db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,1,'OPEN','IN_PROGRESS',%s,'Work started',%s,%s)", (uuid.uuid4(), action, project, owner, created, uuid.uuid4()))
                            db.execute("UPDATE plm.hnd_action_items SET action_state='IN_PROGRESS',updated_by=%s,updated_at=%s,lock_version=1 WHERE action_item_id=%s", (owner, created, action))
                            db.execute("INSERT INTO plm.hnd_action_response_refs(action_response_ref_id,action_item_id,project_id,document_id,document_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,0)", (uuid.uuid4(), action, project, source.document_id, source.document_version_id))
                            db.execute("INSERT INTO plm.hnd_action_evidence_refs(action_evidence_ref_id,action_item_id,project_id,evidence_id,purpose,ordinal) VALUES (%s,%s,%s,%s,'SUBMISSION',0)", (uuid.uuid4(), action, project, submission_evidence))
                            db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,2,'IN_PROGRESS','SUBMITTED',%s,'Response submitted',%s,%s)", (uuid.uuid4(), action, project, owner, created, uuid.uuid4()))
                            db.execute("UPDATE plm.hnd_action_items SET action_state='SUBMITTED',submitted_at=%s,updated_by=%s,updated_at=%s,lock_version=2 WHERE action_item_id=%s", (created, owner, created, action))
                        return action

                    pm_action = seed_action("PM verify")
                    cm_action = seed_action("CM verify")
                    denied_action = seed_action("IM denied")
                    invalid_action = seed_action("Invalid evidence")
                    rollback_action = seed_action("Rollback verify")
                    concurrent_action = seed_action("Concurrent verify")

                guard = Guard()
                authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
                common = dict(unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(), license_guard=guard, authorization=authorization, sources=HandoverSourceValidator(SqlAlchemyDocumentReadRepository()), evidence=SqlAlchemyEvidenceFixedSourceRepository(), repository=SqlAlchemyHandoverActionVerifyRepository(), receipts=SqlAlchemyIdempotencyReceipts(), audit=AuditService(SqlAlchemyAuditRepository()))
                def service(audit=None, license_guard=None):
                    values = dict(common)
                    if audit is not None: values["audit"] = audit
                    if license_guard is not None: values["license_guard"] = license_guard
                    return HandoverActionVerifyService(**values)
                def verify(token, action, expected, key, refs=(verification_evidence,), reason="Response verified"):
                    return service().verify(VerifyHandoverAction(token, CSRF, uuid.uuid4(), project, action, expected, refs, reason, key))

                first = verify(pm_token, pm_action, 2, "manager-verify-0001")
                assert first.action_state == "VERIFIED" and first.etag == '"v3"'
                assert verify(pm_token, pm_action, 2, "manager-verify-0001") == first
                expect("CONFLICT_IDEMPOTENCY", lambda: verify(pm_token, pm_action, 2, "manager-verify-0001", reason="Changed"))
                assert verify(cm_token, cm_action, 2, "customer-manager-verify-0001").etag == '"v3"'
                expect("RESOURCE_NOT_FOUND", lambda: verify(im_token, denied_action, 2, "implementer-verify-0001"))
                expect("HANDOVER_ACTION_STATE_INVALID", lambda: verify(pm_token, pm_action, 3, "repeat-action-verify-0001"))
                expect("CONFLICT_VERSION", lambda: verify(pm_token, rollback_action, 1, "stale-action-verify-0001"))
                expect("HANDOVER_ACTION_EVIDENCE_REQUIRED", lambda: verify(pm_token, invalid_action, 2, "invalid-evidence-verify-0001", refs=(unrelated_evidence,)))

                failed = VerifyHandoverAction(pm_token, CSRF, uuid.uuid4(), project, rollback_action, 2, (verification_evidence,), "Rollback then recover", "rollback-action-verify-0001")
                expect("HANDOVER_UNAVAILABLE", lambda: service(audit=FailedAudit()).verify(failed))
                assert service().verify(failed).etag == '"v3"'
                expired = Guard(); expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service(license_guard=expired).verify(replace(failed, action_item_id=invalid_action, idempotency_key="denied-action-verify-0001")))

                concurrent = VerifyHandoverAction(cm_token, CSRF, uuid.uuid4(), project, concurrent_action, 2, (verification_evidence,), "Concurrent verify", "concurrent-action-verify-0001")
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: service().verify(concurrent), range(2)))
                assert results[0] == results[1]

                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_items WHERE action_state='VERIFIED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_evidence_refs WHERE purpose='VERIFICATION'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_VERIFIED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_HND_ACTION_VERIFY' AND state='COMPLETED'").fetchone()[0] == 4
                print("HND_02_A03_A06_ACTION_VERIFY_PASS: ProjectManager/CustomerManager authorization, current response and submission Evidence revalidation, appended verification Evidence, atomic VERIFIED history, idempotency/concurrency, rollback recovery and License denial verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
