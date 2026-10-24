"""Read real failed Job+Lease+Attempt+Owner audit, NEVER infer commit from STALE."""
from dataclasses import dataclass
from uuid import UUID
from .worker_termination import AuditExportWorkerTermination, TERMINAL_REASONS
from .worker_capture import AuditExportCaptureCommand, AuditExportWorkerCapture, AuditExportWorkerError
from .submit_export import AcceptedAuditExport
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult
from plm_assistant.modules.jobs.application.failure_proof import FailedJobProof
from plm_assistant.modules.jobs.application.lease import JobLeaseError


@dataclass(frozen=True,slots=True)
class VerifiedAuditExportTermination:
    failure: AuditExportFailureResult
    audit_event_id: UUID

    def __post_init__(self):
        if (type(self.failure) is not AuditExportFailureResult or self.failure.state!='FAILED'
                or type(self.audit_event_id) is not UUID or not self.audit_event_id.int):raise AuditExportWorkerError()


class AuditExportTerminationVerification(AuditExportWorkerTermination):
    def __init__(self,*,failure_proofs,**deps):
        if failure_proofs is None:raise ValueError('Owned Audit failure proof required')
        super().__init__(**deps);self._proofs=failure_proofs

    def verify(self,command,*,reason_code):
        if type(command) is not AuditExportCaptureCommand or type(reason_code) is not str or reason_code not in TERMINAL_REASONS:
            raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._verify(command,reason_code)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,JobLeaseError):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _verify(self,c,reason):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.get_created(tx,export_id=c.export_id);AuditExportWorkerCapture._intent(intent,c)
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            request=AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version)
            refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
            proof=self._failure.assert_failed(tx,request=request,refs=refs,fencing_token=c.fencing_token,
                worker_ref=c.worker_ref,error_code=reason)
            if type(proof) is not FailedJobProof:raise AuditExportWorkerError()
            proof.__post_init__()
            event_id=self._proofs.assert_failure(tx,accepted=accepted,identity=identity,reason_code=reason,completed_at=proof.completed_at)
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            # No commit/mutation. A DTO is returned only after both actual owned proofs.
            return VerifiedAuditExportTermination(AuditExportFailureResult(proof.claim,'FAILED'),event_id)
