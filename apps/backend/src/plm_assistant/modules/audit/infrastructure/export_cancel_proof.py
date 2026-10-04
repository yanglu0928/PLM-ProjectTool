"""Audit-owned unique cancellation completion source; no Job private table access."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from .audit_orm import AuditEventRow
from .audit_read_repository import _session
from ..application.worker_capture import AuditExportWorkerError
from ..application.submit_export import AcceptedAuditExport


class SqlAlchemyAuditExportCancelProof:
    def assert_completion(self,tx,*,accepted,identity,expired,completed_at,requested_at,first_request_event_id):
        if (type(accepted) is not AcceptedAuditExport or type(identity) is not UUID or not identity.int
                or type(first_request_event_id) is not UUID or not first_request_event_id.int
                or type(expired) is not bool or any(type(t) is not datetime or t.tzinfo is None
                or t.utcoffset() is None for t in (completed_at,requested_at))):raise AuditExportWorkerError()
        accepted.__post_init__();intent=accepted.intent
        rows=_session(tx).scalars(select(AuditEventRow).where(
            AuditEventRow.action.in_(('AUDIT_EXPORT_CANCELLED','AUDIT_EXPORT_CANCEL_RECOVERED')),
            AuditEventRow.target_owner_module=='jobs',AuditEventRow.target_object_type=='JOB-01',
            AuditEventRow.target_object_id==accepted.job_id).limit(2)).all()
        if len(rows)!=1:raise AuditExportWorkerError()
        r=rows[0]
        first=_session(tx).scalar(select(AuditEventRow).where(AuditEventRow.audit_event_id==first_request_event_id))
        if (first is None or first.action!='AUDIT_EXPORT_CANCEL_REQUESTED'
                or first.target_object_id!=accepted.job_id or first.target_owner_module!='jobs'
                or first.target_object_type!='JOB-01'
                or not requested_at<=first.occurred_at<=r.occurred_at):raise AuditExportWorkerError()
        action='AUDIT_EXPORT_CANCEL_RECOVERED' if expired else 'AUDIT_EXPORT_CANCELLED'
        reason='LEASE_EXPIRED' if expired else 'USER_REQUESTED'
        if ((r.action,r.trace_id,r.event_scope,r.target_project_id,r.actor_type,r.actor_id,r.original_actor_id,
                r.actor_hint_digest,r.outcome,r.target_version_id,r.reason_code,r.before_state,r.after_state)
                !=(action,intent.trace_id,intent.spec.scope,intent.spec.project_id,'SYSTEM',identity,intent.actor_id,
                    None,'SUCCESS',None,reason,'CANCEL_REQUESTED','CANCELLED')
                or not accepted.accepted_at<=requested_at<=r.occurred_at<=completed_at):raise AuditExportWorkerError()
        return r.audit_event_id
