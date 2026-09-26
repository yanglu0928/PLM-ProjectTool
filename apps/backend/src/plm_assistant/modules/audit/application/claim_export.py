"""Admit only actual accepted original Root/Job-Outbox; candidate never authorizes work."""
from dataclasses import dataclass
from uuid import UUID
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerError
from .submit_export import AuditExportIntent,AcceptedAuditExport,AuditExportSubmitService
from .heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaimCandidate,validate_claim_input
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError


@dataclass(frozen=True,slots=True)
class ClaimedAuditExport:
    command: AuditExportCaptureCommand
    claim: ClaimedJob

    def __post_init__(self):
        if (type(self.command) is not AuditExportCaptureCommand or type(self.claim) is not ClaimedJob
                or (self.command.job_id,self.command.fencing_token)!=(self.claim.job_id,self.claim.fencing_token)
                or self.claim.job_type!='AUDIT_EXPORT' or type(self.claim.attempt_no) is not int or not 1<=self.claim.attempt_no<=3
                or type(self.claim.payload_refs) is not dict or self.claim.payload_refs.get('export_id')!=str(self.command.export_id)):
            raise AuditExportWorkerError()
        self.command.__post_init__()


class _UnconfirmedClaim(Exception):
    def __init__(self,result,identity):
        super().__init__('AUDIT_UNAVAILABLE');self.result,self.identity=result,identity


class AuditExportClaimAdmission:
    def __init__(self,*,unit_of_work,repository,claims,queue,system_actor,supervisor):
        if any(d is None for d in (unit_of_work,repository,claims,queue,system_actor)) or type(supervisor) is not AuditHeartbeatSupervisor:
            raise ValueError('Owned admission dependencies required')
        self._uow,self._repo,self._claims,self._queue,self._actor,self._supervisor=unit_of_work,repository,claims,queue,system_actor,supervisor

    def _identity(self):
        try:
            value=self._actor.assert_current()
            if type(value) is not UUID or not value.int:raise ValueError()
            return value
        except Exception:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE') from None

    def claim_next(self,*,worker_ref,lease_seconds=60):
        try:validate_claim_input(worker_ref,lease_seconds)
        except JobLeaseError as exc:raise AuditExportWorkerError(exc.code) from None
        for attempt in range(3):
            try:
                claimed=self._claim(worker_ref,lease_seconds)
                if claimed is False:continue  # Actual eligibility race; fresh UOW/candidate.
                return claimed
            except _UnconfirmedClaim as exc:
                try:return self._confirm(exc.result,exc.identity)
                except Exception:raise AuditExportWorkerError() from None
            except Exception as exc:
                if self._repo.is_retryable_deadlock(exc) is True and attempt<2:continue
                if isinstance(exc,AuditExportWorkerError):raise
                if isinstance(exc,JobLeaseError):raise AuditExportWorkerError(exc.code) from None
                raise AuditExportWorkerError() from None
        return None  # Bounded contention, not a proof the entire queue is empty.

    def _claim(self,worker_ref,seconds):
        identity=self._identity()
        with self._uow() as tx:
            candidate=self._claims.reserve_next(tx)
            if candidate is None:
                if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
                return None
            if type(candidate) is not AuditExportClaimCandidate:raise AuditExportWorkerError()
            candidate.__post_init__()
            hint=AuditExportCaptureCommand(candidate.export_id,candidate.job_id,candidate.current_fencing_token+1,worker_ref)
            with self._supervisor.stopped(hint):
                intent=self._repo.get_created(tx,export_id=candidate.export_id)
                if type(intent) is not AuditExportIntent or intent.export_id!=candidate.export_id:raise AuditExportWorkerError()
                intent.__post_init__();accepted=self._repo.get_accepted(tx,intent=intent)
                if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=candidate.job_id:raise AuditExportWorkerError()
                accepted.__post_init__()
                request=AuditExportSubmitService._queue_request(intent);refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
                actual=self._queue.find_export(tx,request=request)
                if type(actual) is not AuditExportJobRef or actual!=refs:raise AuditExportWorkerError()
                actual.__post_init__()
                if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
                claim=self._claims.claim_target(tx,job_id=candidate.job_id,worker_ref=worker_ref,lease_seconds=seconds)
                if claim is None:return False
                AuditExportJobCompletion._claim(claim,request,refs,claim.fencing_token)
                command=AuditExportCaptureCommand(intent.export_id,claim.job_id,claim.fencing_token,worker_ref)
                result=ClaimedAuditExport(command,claim)
                try:tx.commit()
                except Exception:raise _UnconfirmedClaim(result,identity) from None
                return result

    def _confirm(self,result,identity):
        result.__post_init__();c=result.command
        with self._supervisor.stopped(c):
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            with self._uow() as tx:
                intent=self._repo.get_created(tx,export_id=c.export_id)
                if type(intent) is not AuditExportIntent or intent.export_id!=c.export_id:raise AuditExportWorkerError()
                intent.__post_init__();accepted=self._repo.get_accepted(tx,intent=intent)
                if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
                accepted.__post_init__()
                request=AuditExportSubmitService._queue_request(intent);refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
                actual=self._queue.find_export(tx,request=request)
                if type(actual) is not AuditExportJobRef or actual!=refs:raise AuditExportWorkerError()
                actual.__post_init__()
                if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
                claim=self._claims.check_target(tx,job_id=c.job_id,fencing_token=c.fencing_token,worker_ref=c.worker_ref)
                AuditExportJobCompletion._claim(claim,request,refs,c.fencing_token)
                if claim!=result.claim:raise AuditExportWorkerError()
                return result
