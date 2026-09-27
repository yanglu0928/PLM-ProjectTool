"""Audit-only historical source; no Job tables or live Worker identity bypass."""
from sqlalchemy import select
from .audit_orm import AuditEventRow
from .audit_read_repository import _session
from ..application.worker_capture import AuditExportWorkerError
from ..application.submit_export import AcceptedAuditExport
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobFailure
from uuid import UUID

class SqlAlchemyAuditUserRetryFailureSources:
    def read_failure(self,tx,*,accepted,failure):
        if type(accepted) is not AcceptedAuditExport or type(failure) is not AuditUserRetryJobFailure:
            raise AuditExportWorkerError()
        accepted.__post_init__(); failure.__post_init__(); intent=accepted.intent
        if accepted.job_id!=failure.job_id or accepted.accepted_at>failure.started_at: raise AuditExportWorkerError()
        rows=_session(tx).scalars(select(AuditEventRow).where(AuditEventRow.action=='AUDIT_EXPORT_FAILED',
            AuditEventRow.target_owner_module=='jobs',AuditEventRow.target_object_type=='JOB-01',
            AuditEventRow.target_object_id==accepted.job_id).limit(2)).all()
        if len(rows)!=1: raise AuditExportWorkerError()
        event=rows[0]
        if (type(event.actor_id) is not UUID or not event.actor_id.int
            or (event.trace_id,event.event_scope,event.target_project_id,event.actor_type,event.original_actor_id,
                event.actor_hint_digest,event.outcome,event.target_version_id,event.reason_code,event.before_state,event.after_state)
            !=(intent.trace_id,intent.spec.scope,intent.spec.project_id,'SYSTEM',intent.actor_id,None,'FAILED',None,
                'AUDIT_UNAVAILABLE','RUNNING','FAILED')
            or not failure.started_at<=event.occurred_at<=failure.completed_at):
            raise AuditExportWorkerError()
        return event.audit_event_id
