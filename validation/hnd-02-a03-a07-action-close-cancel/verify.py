"""Windows 11/PostgreSQL 18 proof for Handover Action CLOSE/CANCEL."""

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
from plm_assistant.modules.handover.application.cancel_action import (
    CancelHandoverAction, HandoverActionCancelError, HandoverActionCancelService,
)
from plm_assistant.modules.handover.application.close_action import (
    CloseHandoverAction, HandoverActionCloseError, HandoverActionCloseService,
)
from plm_assistant.modules.handover.infrastructure.action_cancel_repository import SqlAlchemyHandoverActionCancelRepository
from plm_assistant.modules.handover.infrastructure.action_close_repository import SqlAlchemyHandoverActionCloseRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.trace.application.resolution_proof import TraceResolutionProofService
from plm_assistant.modules.trace.application.target_proof import TraceTargetProof, TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.resolution_repository import SqlAlchemyTraceResolutionRepository


ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_close_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


class Owner:
    def prove(self, transaction, query, ref):
        return TraceTargetProof(ref)


def expect(error_type, code, action):
    try:
        action()
    except error_type as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("expected " + code)


def main():
    name = "hnd02a03a07_" + uuid.uuid4().hex[:8]
    pm_token, cm_token = b"p" * 32, b"m" * 32
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
                    pm = seed_user(db, "Close PM", "NONE", pm_token)
                    cm = seed_user(db, "Close CM", "NONE", cm_token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDCLOSE','hndclose','Close Action',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER'),(%s,%s,%s,'CUSTOMER_MANAGER')", (project, pm, department, project, cm, department))
                    document = p01.seed_project_document(db, pm, project, "close-source")
                    evidence = uuid.uuid4()
                    analysis, analysis_version, item = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Close evidence','ELIGIBLE','fixture',%s)", (evidence, project, document.document_id, document.document_version_id, b'e' * 32, pm))
                        db.execute("INSERT INTO plm.hnd_analyses(handover_analysis_id,project_id,analysis_purpose,source_set_ref,analysis_state,created_by) VALUES (%s,%s,'Close fixture',%s,'ACTIVE',%s)", (analysis, project, 'sha256:' + 'a' * 64, pm))
                        db.execute("INSERT INTO plm.hnd_analysis_versions(handover_analysis_version_id,handover_analysis_id,project_id,version_no,version_state,source_set_ref,capability_baseline_id,capability_baseline_version_ref,content_fingerprint,declared_source_count,declared_item_count,declared_evidence_count,declared_capability_ref_count,declared_ai_task_count,created_by) VALUES (%s,%s,%s,1,'APPROVED',%s,%s,%s,%s,1,1,1,0,0,%s)", (analysis_version, analysis, project, 'sha256:' + 'b' * 64, uuid.uuid4(), uuid.uuid4(), b'a' * 32, pm))
                        db.execute("INSERT INTO plm.hnd_analysis_items(analysis_item_row_id,handover_analysis_version_id,handover_analysis_id,project_id,analysis_item_id,ordinal,item_type,title,statement,impact,severity,priority,required_input_spec,source_missing,item_state) VALUES (%s,%s,%s,%s,%s,0,'NEED_CONFIRM','Close item','Resolve item','Required for close','HIGH','HIGH','{}'::jsonb,false,'CONFIRMED')", (uuid.uuid4(), analysis_version, analysis, project, item))

                    def seed_action(title, state="VERIFIED", source_kind="HUMAN"):
                        action, created = uuid.uuid4(), None
                        version = {"OPEN": 0, "IN_PROGRESS": 1, "SUBMITTED": 2, "VERIFIED": 3}[state]
                        source_values = (analysis_version, item, None) if source_kind == "ANALYSIS_ITEM" else (None, None, "Meeting action")
                        with db.transaction():
                            db.execute("SET LOCAL session_replication_role='replica'")
                            db.execute("INSERT INTO plm.hnd_action_items(action_item_id,project_id,source_kind,source_analysis_version_ref,source_item_id,human_source_reason,action_type,title,requested_input_spec,owner_ref,due_at,priority,action_state,submitted_at,verified_by,verified_at,created_by,created_reason,updated_by,lock_version) VALUES (%s,%s,%s,%s,%s,%s,'OTHER',%s,'{}'::jsonb,%s,statement_timestamp()+interval '7 days','LOW',%s,CASE WHEN %s>=2 THEN statement_timestamp() END,CASE WHEN %s>=3 THEN %s END,CASE WHEN %s>=3 THEN statement_timestamp() END,%s,'Fixture action',%s,%s) RETURNING created_at", (action, project, source_kind, *source_values, title, pm, state, version, version, pm, version, pm, pm, version))
                            created = db.execute("SELECT created_at FROM plm.hnd_action_items WHERE action_item_id=%s", (action,)).fetchone()[0]
                            db.execute("UPDATE plm.hnd_action_items SET submitted_at=CASE WHEN %s>=2 THEN %s END,verified_at=CASE WHEN %s>=3 THEN %s END,updated_at=%s WHERE action_item_id=%s", (version, created, version, created, created, action))
                            transitions = [(None, "OPEN"), ("OPEN", "IN_PROGRESS"), ("IN_PROGRESS", "SUBMITTED"), ("SUBMITTED", "VERIFIED")]
                            for sequence, (before, after) in enumerate(transitions[:version + 1]):
                                reason = "Fixture action" if sequence == 0 else "Fixture transition"
                                db.execute("INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (uuid.uuid4(), action, project, sequence, before, after, pm, reason, created, uuid.uuid4()))
                            if version >= 2:
                                db.execute("INSERT INTO plm.hnd_action_response_refs(action_response_ref_id,action_item_id,project_id,document_id,document_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,0)", (uuid.uuid4(), action, project, document.document_id, document.document_version_id))
                                db.execute("INSERT INTO plm.hnd_action_evidence_refs(action_evidence_ref_id,action_item_id,project_id,evidence_id,purpose,ordinal) VALUES (%s,%s,%s,%s,'SUBMISSION',0)", (uuid.uuid4(), action, project, evidence))
                            if version >= 3:
                                db.execute("INSERT INTO plm.hnd_action_evidence_refs(action_evidence_ref_id,action_item_id,project_id,evidence_id,purpose,ordinal) VALUES (%s,%s,%s,%s,'VERIFICATION',1)", (uuid.uuid4(), action, project, evidence))
                        return action, version

                    human_action, _ = seed_action("Human close")
                    analysis_action, _ = seed_action("Analysis close", source_kind="ANALYSIS_ITEM")
                    invalid_action, _ = seed_action("Invalid close")
                    rollback_action, _ = seed_action("Rollback close")
                    concurrent_action, _ = seed_action("Concurrent close")
                    cancel_open, open_version = seed_action("Cancel open", "OPEN")
                    cancel_verified, verified_version = seed_action("Cancel verified", "VERIFIED")
                    cancel_denied, _ = seed_action("Cancel denied", "OPEN")

                    def trace(source_owner, source_type, source_object, source_version, target_owner="requirement", target_type="REQ-03"):
                        link = uuid.uuid4()
                        db.execute("INSERT INTO plm.trc_links(trace_link_id,scope,project_id,source_owner_module,source_object_type,source_object_id,source_version_id,source_project_id,target_owner_module,target_object_type,target_object_id,target_version_id,target_project_id,relation_type,created_by,trace_id) VALUES (%s,'PROJECT',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'REFINES',%s,%s)", (link, project, source_owner, source_type, source_object, source_version, project, target_owner, target_type, uuid.uuid4(), uuid.uuid4(), project, pm, uuid.uuid4()))
                        return link
                    human_trace = trace("document", "DOC-02", document.document_id, document.document_version_id)
                    analysis_trace = trace("handover", "HND-02", analysis, analysis_version)
                    invalid_trace = trace("document", "DOC-02", document.document_id, document.document_version_id, "document", "DOC-02")
                    rollback_trace = trace("document", "DOC-02", document.document_id, document.document_version_id)
                    concurrent_trace = trace("document", "DOC-02", document.document_id, document.document_version_id)

                guard = Guard()
                authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
                owner = Owner()
                proofs = TraceResolutionProofService(
                    SqlAlchemyTraceResolutionRepository(),
                    TraceTargetProofService({
                        ("document", "DOC-02"): owner,
                        ("handover", "HND-02"): owner,
                        ("requirement", "REQ-03"): owner,
                    }),
                )
                common = dict(unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(), license_guard=guard, authorization=authorization, receipts=SqlAlchemyIdempotencyReceipts(), audit=AuditService(SqlAlchemyAuditRepository()))
                def close_service(audit=None, license_guard=None):
                    values = dict(common, trace_proofs=proofs, repository=SqlAlchemyHandoverActionCloseRepository())
                    if audit is not None: values["audit"] = audit
                    if license_guard is not None: values["license_guard"] = license_guard
                    return HandoverActionCloseService(**values)
                def cancel_service(license_guard=None):
                    values = dict(common, repository=SqlAlchemyHandoverActionCancelRepository())
                    if license_guard is not None: values["license_guard"] = license_guard
                    return HandoverActionCancelService(**values)
                def close(token, action, link, key, reason="Resolution accepted"):
                    return close_service().close(CloseHandoverAction(token, CSRF, uuid.uuid4(), project, action, 3, link, reason, key))
                def cancel(token, action, version, key, reason="Action withdrawn"):
                    return cancel_service().cancel(CancelHandoverAction(token, CSRF, uuid.uuid4(), project, action, version, reason, key))

                first = close(pm_token, human_action, human_trace, "human-close-0001")
                assert first.action_state == "CLOSED" and first.etag == '"v4"'
                assert close(pm_token, human_action, human_trace, "human-close-0001") == first
                assert close(pm_token, analysis_action, analysis_trace, "analysis-close-0001").etag == '"v4"'
                expect(HandoverActionCloseError, "RESOURCE_NOT_FOUND", lambda: close(cm_token, invalid_action, invalid_trace, "cm-denied-close-0001"))
                expect(HandoverActionCloseError, "HANDOVER_ACTION_RESOLUTION_REQUIRED", lambda: close(pm_token, invalid_action, invalid_trace, "invalid-close-0001"))
                failed = CloseHandoverAction(pm_token, CSRF, uuid.uuid4(), project, rollback_action, 3, rollback_trace, "Rollback close", "rollback-close-0001")
                expect(HandoverActionCloseError, "HANDOVER_UNAVAILABLE", lambda: close_service(audit=FailedAudit()).close(failed))
                assert close_service().close(failed).etag == '"v4"'
                concurrent = CloseHandoverAction(pm_token, CSRF, uuid.uuid4(), project, concurrent_action, 3, concurrent_trace, "Concurrent close", "concurrent-close-0001")
                with ThreadPoolExecutor(max_workers=2) as pool:
                    closed = list(pool.map(lambda _: close_service().close(concurrent), range(2)))
                assert closed[0] == closed[1]

                cancelled_open = cancel(pm_token, cancel_open, open_version, "cancel-open-0001")
                assert cancelled_open.previous_state == "OPEN" and cancelled_open.etag == '"v1"'
                assert cancel(pm_token, cancel_open, open_version, "cancel-open-0001") == cancelled_open
                cancelled_verified = cancel(pm_token, cancel_verified, verified_version, "cancel-verified-0001")
                assert cancelled_verified.previous_state == "VERIFIED" and cancelled_verified.etag == '"v4"'
                expect(HandoverActionCancelError, "RESOURCE_NOT_FOUND", lambda: cancel(cm_token, cancel_denied, 0, "cm-denied-cancel-0001"))
                expect(HandoverActionCancelError, "HANDOVER_ACTION_STATE_INVALID", lambda: cancel(pm_token, cancel_open, 1, "repeat-cancel-0001"))
                expired = Guard(); expired.enabled = False
                denied = CancelHandoverAction(pm_token, CSRF, uuid.uuid4(), project, cancel_denied, 0, "Denied cancel", "denied-cancel-0001")
                expect(HandoverActionCancelError, "LICENSE_OPERATION_DENIED", lambda: cancel_service(expired).cancel(denied))

                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_items WHERE action_state='CLOSED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.hnd_action_items WHERE action_state='CANCELLED'").fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_CLOSED'").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_CANCELLED'").fetchone()[0] == 2
                    preserved = db.execute("SELECT submitted_at IS NOT NULL,verified_at IS NOT NULL,closed_at IS NULL,resolution_trace_ref IS NULL FROM plm.hnd_action_items WHERE action_item_id=%s", (cancel_verified,)).fetchone()
                    assert preserved == (True, True, True, True), preserved
                print("HND_02_A03_A07_ACTION_CLOSE_CANCEL_PASS: PM-only close/cancel, exact HND-02 and explicit formal downstream Trace proof, terminal integrity, first-result replay/concurrency, rollback, preserved cancellation history and License denial verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
