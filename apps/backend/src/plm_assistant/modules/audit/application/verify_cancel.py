"""Read actual first USER source + terminal owned facts + unique SYSTEM source."""
from dataclasses import dataclass
from uuid import UUID
from .worker_cancel import AuditExportWorkerCancel
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from .submit_export import AcceptedAuditExport,AuditExportSubmitService
from .request_export_cancel import AuditExportCancelReceipt
from plm_assistant.modules.jobs.application.audit_export_cancel import (
    AuditExportCancellationTarget,AuditExportCancellationError,AuditExportCancellationResult,AuditExportCancelFacts,
)
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.cancellation_proof import CancelledJobProof
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion


@dataclass(frozen=True,slots=True)
class VerifiedAuditExportCancellation:
    cancellation: AuditExportCancellationResult
    first_request_event_id: UUID
    completion_event_id: UUID
    expired: bool

    def __post_init__(self):
        if (type(self.cancellation) is not AuditExportCancellationResult or self.cancellation.state!='CANCELLED'
                or self.cancellation.changed is not True or type(self.expired) is not bool
                or any(type(v) is not UUID or not v.int for v in (self.first_request_event_id,self.completion_event_id))
                or self.first_request_event_id==self.completion_event_id):raise AuditExportWorkerError()
        self.cancellation.__post_init__()


class AuditExportCancelVerification(AuditExportWorkerCancel):
    def __init__(self,*,completion_proofs,**deps):
        if completion_proofs is None:raise ValueError('Owned Audit completion proof required')
        super().__init__(**deps);self._proofs=completion_proofs

    def verify(self,command,*,expired):
        if type(command) is not AuditExportCaptureCommand or type(expired) is not bool:raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._verify(command,expired)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,AuditExportCancellationError):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _verify(self,c,expired):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.get_created(tx,export_id=c.export_id);AuditExportWorkerCapture._intent(intent,c)
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            target=AuditExportCancellationTarget(AuditExportSubmitService._queue_request(intent),AuditExportJobRef(accepted.job_id,accepted.event_id))
            facts=self._cancel.read_facts(tx,target=target)
            if type(facts) is not AuditExportCancelFacts or facts.job_id!=c.job_id or facts.state!='CANCELLED':raise AuditExportWorkerError('STALE_LEASE')
            facts.__post_init__()
            first=self._sources.first_request(tx,accepted=accepted,facts=facts)
            if type(first) is not AuditExportCancelReceipt or first.job_id!=c.job_id or first.state!='CANCEL_REQUESTED' or first.changed is not True:raise AuditExportWorkerError()
            first.__post_init__()
            proof=self._cancel.assert_cancelled(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            if type(proof) is not CancelledJobProof:raise AuditExportWorkerError()
            proof.__post_init__()
            AuditExportJobCompletion._claim(proof.claim,target.request,target.refs,c.fencing_token)
            if proof.claim.attempt_no>3 or proof.lease_state!=('EXPIRED' if expired else 'RELEASED'):raise AuditExportWorkerError()
            event_id=self._proofs.assert_completion(tx,accepted=accepted,identity=identity,expired=expired,
                completed_at=proof.completed_at,requested_at=facts.requested_at,first_request_event_id=first.audit_event_id)
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            return VerifiedAuditExportCancellation(AuditExportCancellationResult(c.job_id,'CANCELLED',True),first.audit_event_id,event_id,expired)
