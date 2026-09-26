"""Audit-owned immutable intent/result persistence; no Job private access."""
from datetime import timezone
from sqlalchemy import insert,select
from sqlalchemy.exc import DBAPIError
from ..application.submit_export import AuditExportIntent,AcceptedAuditExport,AuditExportSubmitError
from ..application.export_contract import AuditExportSpec,EXPORT_FORMAT,EXPORT_POLICY_VERSION,EXPORT_PROJECTION_VERSION
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from .audit_read_repository import _session
from .audit_orm import AuditEventRow
from .export_orm import exports,acceptances


class SqlAlchemyAuditExportSubmitRepository:
    @staticmethod
    def is_retryable_deadlock(error):
        # Preserve actual 40P01 through safe Auth/Owner wrappers, never infer from code/text.
        seen=set()
        for _ in range(16):
            if not isinstance(error,BaseException) or id(error) in seen:return False
            seen.add(id(error))
            if isinstance(error,DBAPIError) and getattr(error.orig,"sqlstate",None)=="40P01":return True
            error=error.__cause__ or error.__context__
        return False

    @staticmethod
    def _intent(row):
        spec=AuditExportSpec(row["scope"],row["project_id"],row["purpose"],row["start_at"],row["end_at"],action=row["action"],outcome=row["outcome"],
            actor_id=row["filter_actor_id"],target_object_type=row["target_object_type"],target_object_id=row["target_object_id"],trace_id=row["filter_trace_id"])
        return AuditExportIntent(row["export_id"],row["actor_id"],row["trace_id"],row["requested_at"].astimezone(timezone.utc),spec,row["intent_hash"],
            row["policy_version"],row["projection_version"],row["format_version"])

    def create_intent(self,tx,*,actor_id,spec,trace_id):
        if type(spec) is not AuditExportSpec:raise AuditExportSubmitError()
        fingerprint=spec.fingerprint()
        values=dict(actor_id=actor_id,scope=spec.scope,project_id=spec.project_id,trace_id=trace_id,purpose=spec.purpose,
            start_at=spec.start_at,end_at=spec.end_at,action=spec.action,outcome=spec.outcome,filter_actor_id=spec.actor_id,
            target_object_type=spec.target_object_type,target_object_id=spec.target_object_id,filter_trace_id=spec.trace_id,
            policy_version=EXPORT_POLICY_VERSION,projection_version=EXPORT_PROJECTION_VERSION,format_version=EXPORT_FORMAT,intent_hash=fingerprint)
        row=_session(tx).execute(insert(exports).values(**values).returning(exports)).mappings().one()
        return self._intent(row)

    def get_created(self,tx,*,export_id):
        row=_session(tx).execute(select(exports).where(exports.c.export_id==export_id).with_for_update()).mappings().one_or_none()
        return None if row is None else self._intent(row)

    def _bind(self,tx,intent):
        if type(intent) is not AuditExportIntent:raise AuditExportSubmitError()
        intent.__post_init__()
        if self.get_created(tx,export_id=intent.export_id)!=intent:raise AuditExportSubmitError()

    def get_accepted(self,tx,*,intent):
        self._bind(tx,intent)
        session=_session(tx)
        row=session.execute(select(acceptances).where(acceptances.c.export_id==intent.export_id)).mappings().one_or_none()
        if row is None:return None
        source=session.scalar(select(AuditEventRow).where(AuditEventRow.audit_event_id==row["request_audit_event_id"]))
        if (source is None or (source.trace_id,source.event_scope,source.target_project_id,source.actor_type,source.actor_id,
                source.action,source.outcome,source.target_owner_module,source.target_object_type,source.target_object_id,
                source.target_version_id,source.reason_code,source.before_state,source.after_state)
                != (intent.trace_id,intent.spec.scope,intent.spec.project_id,"USER",intent.actor_id,
                    "AUDIT_EXPORT_REQUESTED","SUCCESS","jobs","JOB-01",row["job_id"],None,intent.spec.purpose,None,"PENDING")
                or not intent.requested_at<=source.occurred_at<=row["accepted_at"]):raise AuditExportSubmitError()
        return AcceptedAuditExport(intent,row["job_id"],row["event_id"],row["request_audit_event_id"],row["accepted_at"].astimezone(timezone.utc))

    def record_acceptance(self,tx,*,intent,queue_ref,audit_event_id):
        self._bind(tx,intent)
        if type(queue_ref) is not AuditExportJobRef:raise AuditExportSubmitError()
        queue_ref.__post_init__()
        _session(tx).execute(insert(acceptances).values(export_id=intent.export_id,job_id=queue_ref.job_id,event_id=queue_ref.event_id,request_audit_event_id=audit_event_id))
        result=self.get_accepted(tx,intent=intent)
        if result is None:raise AuditExportSubmitError()
        return result
