"""Fixed bounded retry policy; current business authority is mandatory, not SYSTEM bypass."""
from uuid import UUID
from .worker_termination import AuditExportWorkerTermination
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from .current_export_authority import AuditExportCurrentAuthorityError
from .export_contract import AuditExportAuthorityRequest
from .submit_export import AcceptedAuditExport,AuditExportSubmitService
from .public import AuditEventDraft
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult
from plm_assistant.modules.jobs.application.lease import JobLeaseError

RETRY_DELAYS={1:5,2:15,3:0}


class AuditExportWorkerRetry(AuditExportWorkerTermination):
    def __init__(self,*,authority,**deps):
        if authority is None:raise ValueError('Current authority required for retry')
        super().__init__(**deps);self._authority=authority

    def retry(self,command,*,reason_code):
        if type(command) is not AuditExportCaptureCommand or type(reason_code) is not str or reason_code!='AUDIT_UNAVAILABLE':
            raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._retry(command)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,(JobLeaseError,AuditExportCurrentAuthorityError)):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _retry(self,c):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.peek_created(tx,export_id=c.export_id);AuditExportWorkerCapture._intent(intent,c)
            authority=AuditExportAuthorityRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,'PUBLISH')
            if self._authority.assert_current(tx,request=authority) is not None:raise AuditExportWorkerError()
            if self._repo.get_created(tx,export_id=c.export_id)!=intent:raise AuditExportWorkerError()
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            request=AuditExportSubmitService._queue_request(intent);refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
            claim=self._failure.inspect_current(tx,request=request,refs=refs,fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            AuditExportJobCompletion._claim(claim,request,refs,c.fencing_token)
            if claim.attempt_no not in RETRY_DELAYS:raise AuditExportWorkerError()
            state='RETRY_WAIT' if claim.attempt_no<3 else 'FAILED'
            event_id=self._audit.append(tx,AuditEventDraft(trace_id=intent.trace_id,event_scope=intent.spec.scope,
                target_project_id=intent.spec.project_id,actor_type='SYSTEM',actor_id=identity,original_actor_id=intent.actor_id,
                actor_hint_digest=None,action='AUDIT_EXPORT_RETRY_SCHEDULED' if state=='RETRY_WAIT' else 'AUDIT_EXPORT_FAILED',
                outcome='FAILED',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=c.job_id,
                reason_code='AUDIT_UNAVAILABLE',before_state='RUNNING',after_state=state))
            if type(event_id) is not UUID or not event_id.int:raise AuditExportWorkerError()
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            if self._authority.assert_current(tx,request=authority) is not None:raise AuditExportWorkerError()
            result=self._failure.fail_current(tx,request=request,refs=refs,fencing_token=c.fencing_token,
                worker_ref=c.worker_ref,error_code='AUDIT_UNAVAILABLE',retryable=True,delay_seconds=RETRY_DELAYS[claim.attempt_no])
            if type(result) is not AuditExportFailureResult or result.claim!=claim or result.state!=state:raise AuditExportWorkerError()
            result.__post_init__();tx.commit();return result
