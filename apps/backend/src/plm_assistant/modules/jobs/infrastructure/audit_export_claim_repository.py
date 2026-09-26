"""Fixed-owner claim; no Root access and no silent exhaustion terminalization."""
from datetime import timedelta
from uuid import UUID
from sqlalchemy import select,and_,or_
from ..application.audit_export_claim import AuditExportClaimCandidate,validate_claim_input
from ..application.lease import JobLeaseError
from .lease_repository import SqlAlchemyJobLeaseRepository
from .orm import JobRow,JobLeaseRow,JobAttemptRow


class SqlAlchemyAuditExportClaimRepository:
    def __init__(self):self._leases=SqlAlchemyJobLeaseRepository()

    def check_target(self,tx,*,job_id,fencing_token,worker_ref):
        claim=self._leases.check_current(tx,job_id=job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        session=self._leases._session(tx)
        job=session.get(JobRow,job_id)
        attempt=self._leases._attempt(session,job_id,fencing_token)
        if (job.owner_module!='audit' or job.job_type!='AUDIT_EXPORT' or job.max_attempts!=3
                or job.completed_at is not None or attempt.error_code is not None or not 1<=claim.attempt_no<=3):raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        return claim

    @staticmethod
    def _eligible(now):
        return (JobRow.owner_module=='audit',JobRow.job_type=='AUDIT_EXPORT',JobRow.attempt_count<JobRow.max_attempts,
            or_(and_(JobRow.state.in_(('PENDING','RETRY_WAIT')),JobRow.available_at<=now),
                and_(JobRow.state=='RUNNING',JobRow.lease_expires_at<=now)))

    def peek_next(self,tx):
        session=self._leases._session(tx);now=self._leases._now(session)
        job=session.scalar(select(JobRow).where(*self._eligible(now)).order_by(JobRow.priority.desc(),JobRow.available_at,JobRow.job_id).limit(1))
        if job is None:return None
        raw=job.payload_refs.get('export_id') if type(job.payload_refs) is dict else None
        if type(raw) is not str:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        try:export_id=UUID(raw)
        except ValueError:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
        if str(export_id)!=raw:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        return AuditExportClaimCandidate(job.job_id,export_id,job.fencing_token)

    def reserve_next(self,tx):
        """Lock only one eligible Job before any upstream locks; never mutate."""
        session=self._leases._session(tx);now=self._leases._now(session)
        job=session.scalar(select(JobRow).where(*self._eligible(now))
            .order_by(JobRow.priority.desc(),JobRow.available_at,JobRow.job_id).limit(1)
            .with_for_update(of=JobRow,skip_locked=True).execution_options(populate_existing=True))
        if job is None:return None
        raw=job.payload_refs.get('export_id') if type(job.payload_refs) is dict else None
        if type(raw) is not str:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        try:export_id=UUID(raw)
        except ValueError:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
        if str(export_id)!=raw:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        return AuditExportClaimCandidate(job.job_id,export_id,job.fencing_token)

    def claim_target(self,tx,*,job_id,worker_ref,lease_seconds):
        validate_claim_input(worker_ref,lease_seconds)
        session=self._leases._session(tx);now=self._leases._now(session)
        job=session.scalar(select(JobRow).where(JobRow.job_id==job_id,*self._eligible(now),JobRow.max_attempts==3)
            .with_for_update(of=JobRow,skip_locked=True).execution_options(populate_existing=True))
        if job is None:return None
        if job.state=='RUNNING':
            lease=self._leases._lease(session,job.job_id,job.fencing_token)
            attempt=self._leases._attempt(session,job.job_id,job.fencing_token)
            if (job.completed_at is not None or lease.lease_expires_at!=job.lease_expires_at or lease.lease_expires_at>now
                    or attempt.attempt_no!=job.attempt_count or attempt.worker_ref!=lease.worker_ref
                    or attempt.completed_at is not None):raise JobLeaseError('INCONSISTENT_LEASE')
            lease.state='EXPIRED';attempt.completed_at=now;attempt.error_code='LEASE_EXPIRED'
        else:
            if (job.completed_at is not None or job.lease_expires_at is not None
                    or session.scalar(select(JobLeaseRow.lease_id).where(JobLeaseRow.job_id==job.job_id,JobLeaseRow.state=='ACTIVE')) is not None):
                raise JobLeaseError('INCONSISTENT_LEASE')
            if job.state=='PENDING' and (job.attempt_count!=0 or job.fencing_token!=0):raise JobLeaseError('INCONSISTENT_ATTEMPT')
        job.attempt_count+=1;job.fencing_token+=1;job.state='RUNNING';job.lease_expires_at=now+timedelta(seconds=lease_seconds)
        session.add(JobLeaseRow(job_id=job.job_id,worker_ref=worker_ref,fencing_token=job.fencing_token,lease_expires_at=job.lease_expires_at))
        session.add(JobAttemptRow(job_id=job.job_id,attempt_no=job.attempt_count,worker_ref=worker_ref,fencing_token=job.fencing_token))
        session.flush()
        return self._leases.check_current(tx,job_id=job.job_id,fencing_token=job.fencing_token,worker_ref=worker_ref)
