"""Expired third-attempt safety failure ONLY, never business or OS kill authority."""
from uuid import UUID
from .worker_termination import AuditExportWorkerTermination
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from .submit_export import AcceptedAuditExport,AuditExportSubmitService
from .public import AuditEventDraft
from .verify_termination import VerifiedAuditExportTermination
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError
from plm_assistant.modules.jobs.application.failure_proof import FailedJobProof

EXHAUSTED_REASON='AUDIT_EXPORT_ATTEMPTS_EXHAUSTED'


class AuditExportWorkerExhaustion(AuditExportWorkerTermination):
    def __init__(self,*,failure_proofs,**deps):
        if failure_proofs is None:raise ValueError('Owned failure source required')
        super().__init__(**deps);self._proofs=failure_proofs

    def expire(self,command):return self._invoke(command,verify=False)
    def verify(self,command):return self._invoke(command,verify=True)

    def _invoke(self,command,*,verify):
        if type(command) is not AuditExportCaptureCommand:raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._run_exhaustion(command,verify)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,JobLeaseError):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _run_exhaustion(self,c,verify):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.get_created(tx,export_id=c.export_id);AuditExportWorkerCapture._intent(intent,c)
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            args=dict(request=AuditExportSubmitService._queue_request(intent),refs=AuditExportJobRef(accepted.job_id,accepted.event_id),fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            value=self._failure.exhaustion(tx,mode='VERIFY' if verify else 'CHECK',**args)
            if verify:
                if type(value) is not FailedJobProof:raise AuditExportWorkerError()
                value.__post_init__()
                if value.error_code!=EXHAUSTED_REASON or value.claim.attempt_no!=3:raise AuditExportWorkerError()
                event=self._proofs.assert_failure(tx,accepted=accepted,identity=identity,reason_code=EXHAUSTED_REASON,completed_at=value.completed_at)
                if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
                return VerifiedAuditExportTermination(AuditExportFailureResult(value.claim,'FAILED'),event)
            if type(value) is not ClaimedJob or value.attempt_no!=3:raise AuditExportWorkerError()
            event=self._audit.append(tx,AuditEventDraft(trace_id=intent.trace_id,event_scope=intent.spec.scope,target_project_id=intent.spec.project_id,
                actor_type='SYSTEM',actor_id=identity,original_actor_id=intent.actor_id,actor_hint_digest=None,action='AUDIT_EXPORT_FAILED',outcome='FAILED',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=c.job_id,reason_code=EXHAUSTED_REASON,before_state='RUNNING',after_state='FAILED'))
            if type(event) is not UUID or not event.int:raise AuditExportWorkerError()
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            after=self._failure.exhaustion(tx,mode='EXPIRE',**args)
            if type(after) is not ClaimedJob or after!=value:raise AuditExportWorkerError()
            tx.commit();return AuditExportFailureResult(after,'FAILED')
