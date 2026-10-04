"""Read a hint then invoke the original safe owner; no batch loop or body work."""
from uuid import UUID
from threading import Lock
from .claim_export import RejectedAuditExportSource,SOURCE_SCAN_REFRESH
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerError
from .verify_termination import VerifiedAuditExportTermination
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCandidate,AuditExportExhaustionScan
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class AuditExportExhaustionSweep:
    def __init__(self,*,unit_of_work,candidates,system_actor,exhaustion):
        if any(d is None for d in (unit_of_work,candidates,system_actor,exhaustion)) or getattr(exhaustion,'_actor',None) is not system_actor:
            raise ValueError('Owned safe sweep and same controlled identity required')
        self._uow,self._candidates,self._actor,self._exhaustion=unit_of_work,candidates,system_actor,exhaustion
        self._cursor,self._scan_lock=None,Lock()
        self._scan_steps=0

    def _identity(self):
        try:
            value=self._actor.assert_current()
            if type(value) is not UUID or not value.int:raise ValueError()
            return value
        except Exception:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE') from None

    def peek_next(self):
        try:
            identity=self._identity()
            with self._uow() as tx:
                candidate=self._candidates.peek_next(tx)
                if candidate is not None:
                    if type(candidate) is not AuditExportExhaustionCandidate:raise AuditExportWorkerError()
                    candidate.__post_init__()
                if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
                return candidate
        except AuditExportWorkerError:raise
        except JobLeaseError as exc:raise AuditExportWorkerError(exc.code) from None
        except Exception:raise AuditExportWorkerError() from None

    def run_next(self,*,isolate_sources=False):
        if type(isolate_sources) is not bool:raise AuditExportWorkerError('VALIDATION_FAILED')
        if not isolate_sources:return self._run_next()
        if not self._scan_lock.acquire(blocking=False):raise AuditExportWorkerError('AUDIT_HEARTBEAT_CAPACITY')
        try:
            if self._scan_steps>=SOURCE_SCAN_REFRESH:self._cursor,self._scan_steps=None,0
            result=self._run_next(True)
            if result is None:self._cursor,self._scan_steps=None,0
            else:
                if type(result) is RejectedAuditExportSource:self._cursor=result.cursor
                self._scan_steps+=1
            return result
        finally:self._scan_lock.release()

    def _run_next(self,isolated=False):
        scanned=None
        if isolated:
            identity=self._identity()
            try:
                with self._uow() as tx:
                    scanned=self._candidates.scan_next(tx,after=self._cursor)
                    if scanned is not None:
                        if type(scanned) is not AuditExportExhaustionScan:raise AuditExportWorkerError()
                        scanned.__post_init__()
                    if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            except AuditExportWorkerError:raise
            except Exception:raise AuditExportWorkerError() from None
            if scanned is not None and scanned.candidate is None:return RejectedAuditExportSource(scanned.cursor,scanned.reason_code)
            candidate=None if scanned is None else scanned.candidate
        else:candidate=self.peek_next()
        if candidate is None:return None
        c=AuditExportCaptureCommand(candidate.export_id,candidate.job_id,candidate.fencing_token,candidate.worker_ref)
        if isolated:
            try:reason=self._exhaustion.inspect_source(c)
            except AuditExportWorkerError:raise
            except Exception:raise AuditExportWorkerError() from None
            if reason is not None:return RejectedAuditExportSource(scanned.cursor,reason)
        try:self._exhaustion.expire(c)
        except Exception as exc:
            try:return self._verify(c)
            except Exception:
                if isinstance(exc,AuditExportWorkerError):raise exc from None
                raise AuditExportWorkerError() from None
        return self._verify(c)

    def _verify(self,c):
        result=self._exhaustion.verify(c)
        if type(result) is not VerifiedAuditExportTermination:raise AuditExportWorkerError()
        result.__post_init__()
        if ((result.failure.claim.job_id,result.failure.claim.fencing_token)!=(c.job_id,c.fencing_token)
                or result.failure.claim.attempt_no!=3):raise AuditExportWorkerError()
        return result
