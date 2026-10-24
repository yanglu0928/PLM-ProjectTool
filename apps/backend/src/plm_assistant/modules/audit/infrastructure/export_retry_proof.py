"""Audit-owned unique event within a real non-overlapping Attempt execution window."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from .audit_orm import AuditEventRow
from .audit_read_repository import _session
from ..application.submit_export import AcceptedAuditExport
from ..application.worker_capture import AuditExportWorkerError


class SqlAlchemyAuditExportRetryProof:
    def assert_retry(self,tx,*,accepted,identity,state,started_at,completed_at):
        if (type(accepted) is not AcceptedAuditExport or type(identity) is not UUID or not identity.int
                or type(state) is not str or state not in {'RETRY_WAIT','FAILED'}
                or any(type(t) is not datetime or t.tzinfo is None or t.utcoffset() is None for t in (started_at,completed_at))
                or started_at>completed_at):raise AuditExportWorkerError()
        accepted.__post_init__();i=accepted.intent
        rows=_session(tx).scalars(select(AuditEventRow).where(
            AuditEventRow.action.in_(('AUDIT_EXPORT_RETRY_SCHEDULED','AUDIT_EXPORT_FAILED')),
            AuditEventRow.target_owner_module=='jobs',AuditEventRow.target_object_type=='JOB-01',AuditEventRow.target_object_id==accepted.job_id,
            AuditEventRow.occurred_at>=started_at,AuditEventRow.occurred_at<=completed_at).limit(2)).all()
        if len(rows)!=1:raise AuditExportWorkerError()
        r=rows[0]
        if ((r.action,r.trace_id,r.event_scope,r.target_project_id,r.actor_type,r.actor_id,r.original_actor_id,
                r.actor_hint_digest,r.outcome,r.target_version_id,r.reason_code,r.before_state,r.after_state)
                !=('AUDIT_EXPORT_RETRY_SCHEDULED' if state=='RETRY_WAIT' else 'AUDIT_EXPORT_FAILED',i.trace_id,
                    i.spec.scope,i.spec.project_id,'SYSTEM',identity,i.actor_id,None,'FAILED',None,'AUDIT_UNAVAILABLE','RUNNING',state)
                or not accepted.accepted_at<=started_at<=r.occurred_at<=completed_at):raise AuditExportWorkerError()
        return r.audit_event_id
