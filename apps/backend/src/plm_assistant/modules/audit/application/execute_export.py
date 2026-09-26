"""One trusted command outcome; no claim loop, guessed commit, or file cleanup."""
from dataclasses import dataclass,field
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerError
from .export_result import AuditExportResult
from .verify_termination import VerifiedAuditExportTermination
from .verify_cancel import VerifiedAuditExportCancellation
from .verify_retry import VerifiedAuditExportRetry
from .worker_termination import TERMINAL_REASONS
from .heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionFacts


@dataclass(frozen=True,slots=True)
class AuditExportExecutionOutcome:
    command: AuditExportCaptureCommand
    kind: str
    value: object=field(repr=False)

    def __post_init__(self):
        if type(self.command) is not AuditExportCaptureCommand or type(self.kind) is not str:raise AuditExportWorkerError()
        self.command.__post_init__();c=self.command;v=self.value
        if self.kind=='SUCCEEDED':
            if type(v) is not AuditExportResult or v.export_id!=c.export_id:raise AuditExportWorkerError()
        elif self.kind=='CANCELLED':
            if type(v) is not VerifiedAuditExportCancellation or v.cancellation.job_id!=c.job_id:raise AuditExportWorkerError()
        elif self.kind=='FAILED' and type(v) is VerifiedAuditExportTermination:
            if (v.failure.claim.job_id,v.failure.claim.fencing_token)!=(c.job_id,c.fencing_token):raise AuditExportWorkerError()
        elif self.kind in {'FAILED','RETRY_SCHEDULED'} and type(v) is VerifiedAuditExportRetry:
            if ((v.transition.claim.job_id,v.transition.claim.fencing_token)!=(c.job_id,c.fencing_token)
                    or v.transition.state!=('FAILED' if self.kind=='FAILED' else 'RETRY_WAIT')):raise AuditExportWorkerError()
        else:raise AuditExportWorkerError()
        v.__post_init__()


class AuditExportExecutor:
    def __init__(self,*,runner,reader,termination,termination_verifier,cancellation,cancellation_verifier,retry,retry_verifier,supervisor):
        deps=(runner,reader,termination,termination_verifier,cancellation,cancellation_verifier,retry,retry_verifier)
        if (type(supervisor) is not AuditHeartbeatSupervisor or any(d is None or getattr(d,'_supervisor',None) is not supervisor for d in deps)
                or getattr(reader,'_actor',None) is None
                or any(getattr(d,'_actor',None) is not reader._actor for d in deps[2:])):
            raise ValueError('One actual supervisor and controlled safety identity required')
        self._runner,self._reader,self._term,self._term_proof,self._cancel,self._cancel_proof,self._retry,self._retry_proof=deps

    @staticmethod
    def _safe(exc):return AuditExportWorkerError(exc.code if isinstance(exc,AuditExportWorkerError) else 'AUDIT_UNAVAILABLE')

    def _facts(self,c):
        facts=self._reader.read(c)
        if type(facts) is not AuditExportExecutionFacts:raise AuditExportWorkerError()
        facts.__post_init__()
        if (facts.claim.job_id,facts.claim.fencing_token)!=(c.job_id,c.fencing_token):raise AuditExportWorkerError()
        return facts

    def _retry_receipt(self,c,attempt):
        value=self._retry_proof.verify(c,attempt_no=attempt)
        if type(value) is not VerifiedAuditExportRetry or value.transition.claim.attempt_no!=attempt:raise AuditExportWorkerError()
        return AuditExportExecutionOutcome(c,'FAILED' if value.transition.state=='FAILED' else 'RETRY_SCHEDULED',value)

    def _terminate(self,c,reason):
        try:self._term.terminate(c,reason_code=reason)
        except Exception as exc:
            try:return AuditExportExecutionOutcome(c,'FAILED',self._term_proof.verify(c,reason_code=reason))
            except Exception:
                fresh=self._facts(c);resolved=self._resolved(c,fresh)
                if resolved is not None:return resolved
                raise self._safe(exc) from None
        return AuditExportExecutionOutcome(c,'FAILED',self._term_proof.verify(c,reason_code=reason))

    def _cancel_once(self,c,expired):
        try:(self._cancel.recover_expired if expired else self._cancel.acknowledge)(c)
        except Exception as exc:
            try:return AuditExportExecutionOutcome(c,'CANCELLED',self._cancel_proof.verify(c,expired=expired))
            except Exception:raise self._safe(exc) from None
        return AuditExportExecutionOutcome(c,'CANCELLED',self._cancel_proof.verify(c,expired=expired))

    def _cancel_requested(self,c,facts):
        expired=not facts.lease_alive
        try:return self._cancel_once(c,expired)
        except AuditExportWorkerError as exc:
            if not expired and exc.code=='STALE_LEASE':
                fresh=self._facts(c)
                if fresh.is_current and fresh.state=='CANCEL_REQUESTED' and fresh.lease_state=='ACTIVE' and not fresh.lease_alive:
                    return self._cancel_once(c,True)
            raise

    def _resolved(self,c,facts):
        if not facts.is_current:
            if facts.error_code=='AUDIT_UNAVAILABLE':return self._retry_receipt(c,facts.claim.attempt_no)
            raise AuditExportWorkerError('STALE_LEASE')
        if facts.state=='SUCCEEDED':return AuditExportExecutionOutcome(c,'SUCCEEDED',self._runner.run(c))
        if facts.state=='CANCELLED' and facts.error_code=='AUDIT_UNAVAILABLE' and facts.claim.attempt_no<3:
            # Immediate cancellation while waiting does not rewrite the original
            # worker's completed retry receipt into a leased cancellation ack.
            return self._retry_receipt(c,facts.claim.attempt_no)
        if facts.state=='CANCELLED':return AuditExportExecutionOutcome(c,'CANCELLED',self._cancel_proof.verify(c,expired=facts.lease_state=='EXPIRED'))
        if facts.state=='CANCEL_REQUESTED':return self._cancel_requested(c,facts)
        if facts.state=='RETRY_WAIT':return self._retry_receipt(c,facts.claim.attempt_no)
        if facts.state=='FAILED':
            if facts.error_code in TERMINAL_REASONS:return AuditExportExecutionOutcome(c,'FAILED',self._term_proof.verify(c,reason_code=facts.error_code))
            if facts.error_code=='AUDIT_UNAVAILABLE':return self._retry_receipt(c,facts.claim.attempt_no)
            raise AuditExportWorkerError()
        return None

    def _schedule_retry(self,c,facts):
        try:self._retry.retry(c,reason_code='AUDIT_UNAVAILABLE')
        except Exception as exc:
            try:return self._retry_receipt(c,facts.claim.attempt_no)
            except Exception:
                error=self._safe(exc)
                fresh=self._facts(c);resolved=self._resolved(c,fresh)
                if resolved is not None:return resolved
                if error.code in TERMINAL_REASONS:
                    if fresh.is_current and fresh.state=='RUNNING' and fresh.lease_alive:return self._terminate(c,error.code)
                raise error from None
        return self._retry_receipt(c,facts.claim.attempt_no)

    def execute(self,command):
        if type(command) is not AuditExportCaptureCommand:raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        try:
            facts=self._facts(command);resolved=self._resolved(command,facts)
            if resolved is not None:return resolved
            if facts.state!='RUNNING' or not facts.lease_alive:raise AuditExportWorkerError('STALE_LEASE')
            try:return AuditExportExecutionOutcome(command,'SUCCEEDED',self._runner.run(command))
            except Exception as exc:
                error=self._safe(exc)
                if error.code=='AUDIT_HEARTBEAT_STOP_TIMEOUT':raise error from None
                fresh=self._facts(command);resolved=self._resolved(command,fresh)
                if resolved is not None:return resolved
                if fresh.state!='RUNNING' or not fresh.is_current or not fresh.lease_alive:raise AuditExportWorkerError('STALE_LEASE')
                if error.code in TERMINAL_REASONS:return self._terminate(command,error.code)
                if error.code=='AUDIT_UNAVAILABLE':return self._schedule_retry(command,fresh)
                raise error from None
        except Exception as exc:raise self._safe(exc) from None
