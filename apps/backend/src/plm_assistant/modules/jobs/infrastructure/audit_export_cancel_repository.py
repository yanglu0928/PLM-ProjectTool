"""Owned Job cancellation under caller UOW, with original pair and active-lease checks."""
from sqlalchemy import select
from ..application.audit_export_cancel import (
    AuditExportCancellationError as Error,AuditExportCancellationResult as Result,
    validate_target,validate_cancel_request,
    AuditExportCancelFacts,
)
from ..application.audit_export_enqueue import AuditExportEnqueueError
from ..application.lease import JobLeaseError
from ..application.lease_checkpoint import validate_checkpoint
from .audit_export_enqueue_repository import SqlAlchemyAuditExportJobQueueRepository
from .lease_repository import SqlAlchemyJobLeaseRepository
from .orm import JobRow,JobLeaseRow


class SqlAlchemyAuditExportCancellationRepository:
    def __init__(self):
        self._queue=SqlAlchemyAuditExportJobQueueRepository()
        self._leases=SqlAlchemyJobLeaseRepository()

    def read_facts(self,transaction,*,target):
        _,job=self._bound(transaction,target)
        return AuditExportCancelFacts(job.job_id,job.state,job.cancel_requested_by,job.cancel_requested_at,job.cancel_reason)

    def _bound(self,tx,target):
        validate_target(target)
        try:
            refs=self._queue.find_export(tx,request=target.request)
            if refs!=target.refs:raise Error("CONFLICT_STATE")
            session=self._leases._session(tx)
            job=session.execute(select(JobRow).where(JobRow.job_id==refs.job_id).with_for_update(of=JobRow)).scalar_one()
            return session,job
        except (AuditExportEnqueueError,JobLeaseError) as exc:
            raise Error(exc.code) from None

    @staticmethod
    def _history(job):
        if any(value is None for value in (job.cancel_requested_by,job.cancel_reason,job.cancel_requested_at)):
            raise Error("CONFLICT_STATE")

    def _active(self,session,job):
        try:
            lease=self._leases._lease(session,job.job_id,job.fencing_token)
            attempt=self._leases._attempt(session,job.job_id,job.fencing_token)
        except JobLeaseError as exc:raise Error(exc.code) from None
        if (job.completed_at is not None or job.lease_expires_at is None or job.lease_expires_at!=lease.lease_expires_at
                or job.attempt_count!=attempt.attempt_no or attempt.completed_at is not None
                or lease.worker_ref!=attempt.worker_ref):raise Error("CONFLICT_STATE")
        return lease,attempt

    @staticmethod
    def _finish(session,job,lease,attempt,now,*,expired):
        lease.state="EXPIRED" if expired else "RELEASED"
        attempt.completed_at=now;attempt.error_code="JOB_CANCELLED"
        job.state="CANCELLED";job.lease_expires_at=None;job.completed_at=now
        session.flush()
        return Result(job.job_id,job.state,True)

    def request_cancel(self,transaction,*,target,requested_by,reason):
        validate_cancel_request(target=target,requested_by=requested_by,reason=reason)
        session,job=self._bound(transaction,target)
        if job.state in {"SUCCEEDED","FAILED"}:return Result(job.job_id,job.state,False)
        if job.state in {"CANCEL_REQUESTED","CANCELLED"}:
            self._history(job)
            return Result(job.job_id,job.state,False)
        if job.state not in {"PENDING","RETRY_WAIT","RUNNING"}:raise Error("CONFLICT_STATE")
        if job.state=="RUNNING":self._active(session,job)
        else:
            if (job.lease_expires_at is not None or job.completed_at is not None
                    or session.scalar(select(JobLeaseRow.lease_id).where(JobLeaseRow.job_id==job.job_id,JobLeaseRow.state=="ACTIVE").with_for_update(of=JobLeaseRow)) is not None):
                raise Error("CONFLICT_STATE")
        immediate=job.state!="RUNNING"
        now=self._leases._now(session)
        job.cancel_requested_by=requested_by;job.cancel_reason=reason;job.cancel_requested_at=now
        job.state="CANCEL_REQUESTED";session.flush()
        if immediate:
            job.state="CANCELLED";job.completed_at=now;session.flush()
        return Result(job.job_id,job.state,True)

    def acknowledge_cancel(self,transaction,*,target,fencing_token,worker_ref):
        validate_target(target)
        try:validate_checkpoint(job_id=target.refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        except JobLeaseError:raise Error("VALIDATION_FAILED") from None
        session,job=self._bound(transaction,target)
        self._history(job)
        if job.state!="CANCEL_REQUESTED" or job.fencing_token!=fencing_token:raise Error("STALE_LEASE")
        lease,attempt=self._active(session,job)
        now=self._leases._now(session)
        if lease.worker_ref!=worker_ref or lease.lease_expires_at<=now:raise Error("STALE_LEASE")
        return self._finish(session,job,lease,attempt,now,expired=False)

    def recover_expired_cancel(self,transaction,*,target):
        session,job=self._bound(transaction,target)
        self._history(job)
        if job.state=="CANCELLED":return Result(job.job_id,job.state,False)
        if job.state!="CANCEL_REQUESTED":raise Error("CONFLICT_STATE")
        lease,attempt=self._active(session,job)
        now=self._leases._now(session)
        if lease.lease_expires_at>now:raise Error("LEASE_NOT_EXPIRED")
        return self._finish(session,job,lease,attempt,now,expired=True)
