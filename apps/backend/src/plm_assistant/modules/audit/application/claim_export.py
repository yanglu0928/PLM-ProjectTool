"""Admit only actual accepted original Root/Job-Outbox; candidate never authorizes work."""
from dataclasses import dataclass
from uuid import UUID
from threading import Lock
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerError
from .submit_export import AuditExportIntent,AcceptedAuditExport,AuditExportSubmitService,AuditExportSourceRejected
from .heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaimCandidate,validate_claim_input
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef,AuditExportEnqueueError
from plm_assistant.modules.jobs.application.audit_export_scan import AuditExportScanCursor,AuditExportScanReservation
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCursor
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError

SOURCE_SCAN_REFRESH=32  # Scheduling actions, not elapsed seconds or authority.


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


@dataclass(frozen=True,slots=True)
class RejectedAuditExportSource:
    cursor: AuditExportScanCursor|AuditExportExhaustionCursor
    reason_code: str

    def __post_init__(self):
        if type(self.cursor) not in (AuditExportScanCursor,AuditExportExhaustionCursor):raise AuditExportWorkerError()
        self.cursor.__post_init__()
        if type(self.reason_code) is not str or self.reason_code not in {
            'INVALID_EXPORT_REF','ROOT_MISSING','ROOT_MISMATCH','ACCEPTANCE_MISSING',
            'ACCEPTANCE_MISMATCH','ACCEPTANCE_SOURCE_INVALID','PAIR_MISMATCH'}:raise AuditExportWorkerError()


class AuditExportClaimAdmission:
    def __init__(self,*,unit_of_work,repository,claims,queue,system_actor,supervisor):
        if any(d is None for d in (unit_of_work,repository,claims,queue,system_actor)) or type(supervisor) is not AuditHeartbeatSupervisor:
            raise ValueError('Owned admission dependencies required')
        self._uow,self._repo,self._claims,self._queue,self._actor,self._supervisor=unit_of_work,repository,claims,queue,system_actor,supervisor
        self._cursor,self._scan_lock=None,Lock()
        self._scan_steps=0

    def _identity(self):
        try:
            value=self._actor.assert_current()
            if type(value) is not UUID or not value.int:raise ValueError()
            return value
        except Exception:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE') from None

    def claim_next(self,*,worker_ref,lease_seconds=60,isolate_sources=False):
        try:validate_claim_input(worker_ref,lease_seconds)
        except JobLeaseError as exc:raise AuditExportWorkerError(exc.code) from None
        if type(isolate_sources) is not bool:raise AuditExportWorkerError('VALIDATION_FAILED')
        if not isolate_sources:return self._next(worker_ref,lease_seconds,False)
        if not self._scan_lock.acquire(blocking=False):raise AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
        try:
            if self._scan_steps>=SOURCE_SCAN_REFRESH:self._cursor,self._scan_steps=None,0
            result=self._next(worker_ref,lease_seconds,True)
            if result is None:self._cursor,self._scan_steps=None,0
            else:
                if type(result) is RejectedAuditExportSource:self._cursor=result.cursor
                self._scan_steps+=1
            return result
        finally:self._scan_lock.release()

    def _next(self,worker_ref,lease_seconds,isolated):
        for attempt in range(3):
            try:
                claimed=self._claim(worker_ref,lease_seconds,isolated)
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

    def _claim(self,worker_ref,seconds,isolated=False):
        identity=self._identity()
        with self._uow() as tx:
            reservation=None
            if isolated:
                reservation=self._claims.scan_next(tx,after=self._cursor)
                if reservation is not None:
                    if type(reservation) is not AuditExportScanReservation:raise AuditExportWorkerError()
                    reservation.__post_init__()
                    if reservation.candidate is None:return self._reject(reservation,identity,reservation.reason_code)
                candidate=None if reservation is None else reservation.candidate
            else:candidate=self._claims.reserve_next(tx)
            if candidate is None:
                if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
                return None
            if type(candidate) is not AuditExportClaimCandidate:raise AuditExportWorkerError()
            candidate.__post_init__()
            hint=AuditExportCaptureCommand(candidate.export_id,candidate.job_id,candidate.current_fencing_token+1,worker_ref)
            with self._supervisor.stopped(hint):
                intent=self._repo.get_created(tx,export_id=candidate.export_id)
                if isolated and intent is None:return self._reject(reservation,identity,'ROOT_MISSING')
                if isolated and type(intent) is AuditExportIntent and intent.export_id!=candidate.export_id:return self._reject(reservation,identity,'ROOT_MISMATCH')
                if type(intent) is not AuditExportIntent or intent.export_id!=candidate.export_id:raise AuditExportWorkerError()
                intent.__post_init__()
                try:accepted=self._repo.get_accepted(tx,intent=intent)
                except AuditExportSourceRejected as exc:
                    if isolated and exc.reason_code=='ACCEPTANCE_SOURCE_INVALID':return self._reject(reservation,identity,exc.reason_code)
                    raise
                if isolated and accepted is None:return self._reject(reservation,identity,'ACCEPTANCE_MISSING')
                if isolated and type(accepted) is AcceptedAuditExport and (accepted.intent!=intent or accepted.job_id!=candidate.job_id):return self._reject(reservation,identity,'ACCEPTANCE_MISMATCH')
                if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=candidate.job_id:raise AuditExportWorkerError()
                accepted.__post_init__()
                request=AuditExportSubmitService._queue_request(intent);refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
                try:actual=self._queue.find_export(tx,request=request)
                except AuditExportEnqueueError as exc:
                    if isolated and exc.code=='CONFLICT_STATE':return self._reject(reservation,identity,'PAIR_MISMATCH')
                    raise
                if isolated and (actual is None or type(actual) is AuditExportJobRef and actual!=refs):return self._reject(reservation,identity,'PAIR_MISMATCH')
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

    def _reject(self,reservation,identity,reason):
        if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
        return RejectedAuditExportSource(reservation.cursor,reason)

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
