"""One bounded scheduling action; stop new admission, drain known owned work."""
from dataclasses import dataclass,field
from threading import Event,Lock
from .claim_export import ClaimedAuditExport
from .execute_export import AuditExportExecutionOutcome
from .verify_termination import VerifiedAuditExportTermination
from .worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_claim import validate_claim_input
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionFacts
from plm_assistant.modules.jobs.application.lease import JobLeaseError


@dataclass(frozen=True,slots=True)
class AuditExportStepOutcome:
    kind: str
    value: object=field(default=None,repr=False)

    def __post_init__(self):
        expected={'IDLE':type(None),'STOPPED':type(None),'EXECUTED':AuditExportExecutionOutcome,
            'SWEEP_FAILED':VerifiedAuditExportTermination,'LEASE_EXPIRED':AuditExportExecutionFacts,'SUPERSEDED':AuditExportExecutionFacts}
        if type(self.kind) is not str or self.kind not in expected or type(self.value) is not expected[self.kind]:raise AuditExportWorkerError()
        if self.value is not None:self.value.__post_init__()


class AuditExportWorkerStep:
    def __init__(self,*,admission,executor,sweep,worker_ref,lease_seconds=60):
        if any(d is None for d in (admission,executor,sweep)):raise ValueError('Owned step dependencies required')
        try:validate_claim_input(worker_ref,lease_seconds)
        except JobLeaseError as exc:raise ValueError('Valid fixed worker and lease required') from None
        actor=getattr(admission,'_actor',None);supervisor=getattr(admission,'_supervisor',None)
        if (actor is None or supervisor is None or getattr(executor._reader,'_actor',None) is not actor
                or getattr(executor._reader,'_supervisor',None) is not supervisor or getattr(sweep,'_actor',None) is not actor
                or getattr(sweep._exhaustion,'_supervisor',None) is not supervisor):raise ValueError('One actual identity and supervisor required')
        self._admission,self._executor,self._sweep=admission,executor,sweep
        self._worker,self._seconds=worker_ref,lease_seconds
        self._stop,self._lock,self._pending,self._failed,self._prefer_sweep=Event(),Lock(),None,False,True

    def request_stop(self):self._stop.set()

    def step(self):
        if not self._lock.acquire(blocking=False):raise AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
        try:
            if self._pending is not None:return self._execute_pending()
            if self._stop.is_set():return AuditExportStepOutcome('STOPPED')
            order=('SWEEP','CLAIM') if self._prefer_sweep else ('CLAIM','SWEEP')
            for operation in order:
                if self._stop.is_set():return AuditExportStepOutcome('STOPPED')
                if operation=='SWEEP':
                    result=self._sweep.run_next()
                    if result is not None:
                        outcome=AuditExportStepOutcome('SWEEP_FAILED',result);self._prefer_sweep=False;return outcome
                else:
                    claim=self._admission.claim_next(worker_ref=self._worker,lease_seconds=self._seconds)
                    if claim is not None:
                        if type(claim) is not ClaimedAuditExport:raise AuditExportWorkerError()
                        claim.__post_init__()
                        if claim.command.worker_ref!=self._worker:raise AuditExportWorkerError()
                        self._pending=claim;self._failed=False;self._prefer_sweep=True
                        return self._execute_pending()
            return AuditExportStepOutcome('IDLE')
        except AuditExportWorkerError:raise
        except Exception:raise AuditExportWorkerError() from None
        finally:self._lock.release()

    def _execute_pending(self):
        pending=self._pending;c=pending.command
        if self._failed:
            facts=self._executor._reader.read(c)
            if type(facts) is not AuditExportExecutionFacts:raise AuditExportWorkerError()
            facts.__post_init__()
            if (facts.claim.job_id,facts.claim.fencing_token)!=(c.job_id,c.fencing_token):raise AuditExportWorkerError()
            kind='SUPERSEDED' if not facts.is_current else ('LEASE_EXPIRED' if facts.state=='RUNNING' and not facts.lease_alive and facts.claim.attempt_no<3 else None)
            if kind:
                result=AuditExportStepOutcome(kind,facts);self._pending=None;self._failed=False;return result
        try:
            result=self._executor.execute(c)
            if type(result) is not AuditExportExecutionOutcome or result.command!=c:raise AuditExportWorkerError()
            outcome=AuditExportStepOutcome('EXECUTED',result)
        except Exception:self._failed=True;raise
        self._pending=None;self._failed=False;return outcome
