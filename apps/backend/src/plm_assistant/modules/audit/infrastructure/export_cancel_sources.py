"""Owned append-only cancel request events double as immutable command receipts."""
from sqlalchemy import select
from .audit_orm import AuditEventRow
from .audit_read_repository import _session
from ..application.request_export_cancel import AuditExportCancelReceipt,AuditExportCancelRequestError as Error
from ..application.submit_export import AcceptedAuditExport
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancelFacts


class SqlAlchemyAuditExportCancelSources:
    @staticmethod
    def _bound(r,accepted):
        if type(accepted) is not AcceptedAuditExport:raise Error()
        accepted.__post_init__()
        i=accepted.intent
        if (r is None or (r.event_scope,r.target_project_id,r.actor_type,r.original_actor_id,r.actor_hint_digest,
                r.outcome,r.target_owner_module,r.target_object_type,r.target_object_id,r.target_version_id,r.reason_code)
                !=(i.spec.scope,i.spec.project_id,'USER',None,None,'SUCCESS','jobs','JOB-01',accepted.job_id,None,'USER_REQUESTED')
                or r.occurred_at<accepted.accepted_at):raise Error()

    def receipt(self,tx,*,accepted,actor_id,audit_event_id):
        r=_session(tx).scalar(select(AuditEventRow).where(AuditEventRow.audit_event_id==audit_event_id))
        self._bound(r,accepted)
        if r.actor_id!=actor_id:raise Error()
        changed=r.action=='AUDIT_EXPORT_CANCEL_REQUESTED'
        if changed:
            expected={'PENDING':'CANCELLED','RETRY_WAIT':'CANCELLED','RUNNING':'CANCEL_REQUESTED'}.get(r.before_state)
            if r.after_state!=expected or expected is None:raise Error()
        elif r.action!='AUDIT_EXPORT_CANCEL_CHECKED' or r.before_state!=r.after_state:raise Error()
        return AuditExportCancelReceipt(accepted.job_id,r.after_state,changed,r.audit_event_id)

    def first_request(self,tx,*,accepted,facts):
        if type(accepted) is not AcceptedAuditExport or type(facts) is not AuditExportCancelFacts or facts.job_id!=accepted.job_id:raise Error()
        accepted.__post_init__();facts.__post_init__()
        rows=_session(tx).scalars(select(AuditEventRow).where(AuditEventRow.action=='AUDIT_EXPORT_CANCEL_REQUESTED',
            AuditEventRow.target_owner_module=='jobs',AuditEventRow.target_object_type=='JOB-01',AuditEventRow.target_object_id==accepted.job_id).limit(2)).all()
        if len(rows)!=1:raise Error()
        r=rows[0];self._bound(r,accepted)
        result=self.receipt(tx,accepted=accepted,actor_id=facts.requested_by,audit_event_id=r.audit_event_id)
        if facts.requested_at is None or r.occurred_at<facts.requested_at:raise Error()
        return result
