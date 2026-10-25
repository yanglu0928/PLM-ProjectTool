"""Read original retry receipt even after a new attempt starts; never change that attempt."""
from dataclasses import dataclass
from uuid import UUID
from .worker_retry import AuditExportWorkerRetry
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from .current_export_authority import AuditExportCurrentAuthorityError
from .export_contract import AuditExportAuthorityRequest
from .submit_export import AcceptedAuditExport,AuditExportSubmitService
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.retry_proof import RetryTransitionProof
from plm_assistant.modules.jobs.application.lease import JobLeaseError


@dataclass(frozen=True,slots=True)
class VerifiedAuditExportRetry:
    transition: RetryTransitionProof
    audit_event_id: UUID

    def __post_init__(self):
        if type(self.transition) is not RetryTransitionProof or type(self.audit_event_id) is not UUID or not self.audit_event_id.int:raise AuditExportWorkerError()
        self.transition.__post_init__()


class AuditExportRetryVerification(AuditExportWorkerRetry):
    def __init__(self,*,retry_proofs,**deps):
        if retry_proofs is None:raise ValueError('Owned retry Audit source required')
        super().__init__(**deps);self._proofs=retry_proofs

    def verify(self,command,*,attempt_no):
        if type(command) is not AuditExportCaptureCommand or type(attempt_no) is not int or not 1<=attempt_no<=3:raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for retry in range(3):
                try:return self._verify(command,attempt_no)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if retry<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,(JobLeaseError,AuditExportCurrentAuthorityError)):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _verify(self,c,attempt_no):
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
            proof=self._failure.assert_retry_transition(tx,request=request,refs=refs,fencing_token=c.fencing_token,
                worker_ref=c.worker_ref,attempt_no=attempt_no)
            if type(proof) is not RetryTransitionProof:raise AuditExportWorkerError()
            proof.__post_init__();AuditExportJobCompletion._claim(proof.claim,request,refs,c.fencing_token)
            if proof.claim.attempt_no!=attempt_no or proof.state!=('FAILED' if attempt_no==3 else 'RETRY_WAIT'):raise AuditExportWorkerError()
            event_id=self._proofs.assert_retry(tx,accepted=accepted,identity=identity,state=proof.state,
                started_at=proof.started_at,completed_at=proof.completed_at)
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            if self._authority.assert_current(tx,request=authority) is not None:raise AuditExportWorkerError()
            return VerifiedAuditExportRetry(proof,event_id)
