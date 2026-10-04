"""Audit-owned minimal fixed-field failure proof; no Job private access."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from .audit_orm import AuditEventRow
from .audit_read_repository import _session
from ..application.worker_capture import AuditExportWorkerError
from ..application.submit_export import AcceptedAuditExport


class SqlAlchemyAuditExportFailureProof:
    def assert_failure(self,tx,*,accepted,identity,reason_code,completed_at):
        if (type(accepted) is not AcceptedAuditExport or type(identity) is not UUID or not identity.int
                or type(completed_at) is not datetime or completed_at.tzinfo is None):raise AuditExportWorkerError()
        accepted.__post_init__();intent=accepted.intent
        rows=_session(tx).scalars(select(AuditEventRow).where(AuditEventRow.action=='AUDIT_EXPORT_FAILED',
            AuditEventRow.target_owner_module=='jobs',AuditEventRow.target_object_type=='JOB-01',
            AuditEventRow.target_object_id==accepted.job_id).limit(2)).all()
        if len(rows)!=1:raise AuditExportWorkerError()
        r=rows[0]
        if ((r.trace_id,r.event_scope,r.target_project_id,r.actor_type,r.actor_id,r.original_actor_id,
                r.actor_hint_digest,r.outcome,r.target_version_id,r.reason_code,r.before_state,r.after_state)
                !=(intent.trace_id,intent.spec.scope,intent.spec.project_id,'SYSTEM',identity,intent.actor_id,
                    None,'FAILED',None,reason_code,'RUNNING','FAILED')
                or not accepted.accepted_at<=r.occurred_at<=completed_at):raise AuditExportWorkerError()
        return r.audit_event_id
