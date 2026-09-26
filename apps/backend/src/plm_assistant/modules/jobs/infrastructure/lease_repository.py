"""PostgreSQL row-lock and fencing implementation for the Job owner."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow, JobLeaseRow, JobRow


class SqlAlchemyJobLeaseRepository:
    def check_succeeded(self, transaction: object, *, job_id: uuid.UUID,
                        fencing_token: int, worker_ref: str) -> ClaimedJob:
        """Read terminal success facts; never accept an expired ACTIVE lease as success."""
        validate_checkpoint(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        session=self._session(transaction)
        job=session.execute(select(JobRow).where(JobRow.job_id==job_id)
            .with_for_update(of=JobRow)).scalar_one_or_none()
        if (job is None or job.state!='SUCCEEDED' or job.fencing_token!=fencing_token
                or job.lease_expires_at is not None or job.completed_at is None):raise JobLeaseError('STALE_LEASE')
        lease=session.execute(select(JobLeaseRow).where(JobLeaseRow.job_id==job_id,
            JobLeaseRow.fencing_token==fencing_token).with_for_update(of=JobLeaseRow)).scalar_one_or_none()
        attempt=self._attempt(session,job_id,fencing_token)
        if (lease is None or lease.state!='RELEASED' or lease.worker_ref!=worker_ref
                or attempt.worker_ref!=worker_ref or attempt.attempt_no!=job.attempt_count
                or attempt.error_code is not None or attempt.completed_at!=job.completed_at
                or not attempt.started_at<=job.completed_at<lease.lease_expires_at
                or lease.acquired_at>job.completed_at):raise JobLeaseError('INCONSISTENT_LEASE')
        return self._claim(job)

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob:
        validate_checkpoint(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        session = self._session(transaction)
        job, lease, attempt = self._current(session, job_id, fencing_token, worker_ref)
        now = self._now(session)
        if (job.lease_expires_at is None or job.lease_expires_at <= now
                or lease.lease_expires_at <= now):
            raise JobLeaseError("STALE_LEASE")
        if (job.lease_expires_at != lease.lease_expires_at
                or job.attempt_count != attempt.attempt_no):
            raise JobLeaseError("INCONSISTENT_LEASE")
        return self._claim(job)

    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> ClaimedJob | None:
        session = self._session(transaction)
        # Limit one claim per transaction. Exhausted jobs are terminalized before
        # trying the next row, so they cannot starve a ready job indefinitely.
        for _ in range(100):
            now = self._now(session)
            job = session.execute(select(JobRow).where(or_(
                and_(JobRow.state.in_(("PENDING", "RETRY_WAIT")), JobRow.available_at <= now),
                and_(JobRow.state == "RUNNING", JobRow.lease_expires_at <= now),
            )).order_by(JobRow.priority.desc(), JobRow.available_at, JobRow.job_id)
                .limit(1).with_for_update(of=JobRow, skip_locked=True)).scalar_one_or_none()
            if job is None:
                return None
            if job.state == "RUNNING":
                previous = self._lease(session, job.job_id, job.fencing_token)
                if previous.lease_expires_at > now:
                    raise JobLeaseError("INCONSISTENT_LEASE")
                previous.state = "EXPIRED"
                attempt = self._attempt(session, job.job_id, job.fencing_token)
                attempt.completed_at = now
                attempt.error_code = "LEASE_EXPIRED"
                session.flush()
            elif session.execute(select(JobLeaseRow.lease_id).where(
                JobLeaseRow.job_id == job.job_id, JobLeaseRow.state == "ACTIVE",
            )).scalar_one_or_none() is not None:
                raise JobLeaseError("INCONSISTENT_LEASE")
            if job.attempt_count >= job.max_attempts:
                job.state = "FAILED"
                job.lease_expires_at = None
                job.completed_at = now
                session.flush()
                continue
            job.attempt_count += 1
            job.fencing_token += 1
            job.state = "RUNNING"
            job.lease_expires_at = now + timedelta(seconds=lease_seconds)
            session.add(JobLeaseRow(job_id=job.job_id, worker_ref=worker_ref,
                                    fencing_token=job.fencing_token,
                                    lease_expires_at=job.lease_expires_at))
            session.add(JobAttemptRow(job_id=job.job_id, attempt_no=job.attempt_count,
                                      worker_ref=worker_ref,
                                      fencing_token=job.fencing_token))
            session.flush()
            return self._claim(job)
        raise JobLeaseError("CLAIM_BATCH_LIMIT")

    def heartbeat(self, transaction: object, *, job_id: uuid.UUID,
                  fencing_token: int, worker_ref: str, lease_seconds: int) -> None:
        session = self._session(transaction)
        job, lease, _ = self._current(session, job_id, fencing_token, worker_ref)
        now = self._now(session)
        if job.lease_expires_at is None or job.lease_expires_at <= now or lease.lease_expires_at <= now:
            raise JobLeaseError("STALE_LEASE")
        until = now + timedelta(seconds=lease_seconds)
        job.lease_expires_at = until
        lease.lease_expires_at = until
        lease.heartbeat_at = now
        session.flush()

    def finish(self, transaction: object, *, job_id: uuid.UUID,
               fencing_token: int, worker_ref: str) -> ClaimedJob:
        session = self._session(transaction)
        job, lease, attempt = self._current(session, job_id, fencing_token, worker_ref)
        now = self._now(session)
        if job.lease_expires_at is None or job.lease_expires_at <= now or lease.lease_expires_at <= now:
            raise JobLeaseError("STALE_LEASE")
        claim = self._claim(job)
        job.state = "SUCCEEDED"
        job.lease_expires_at = None
        job.completed_at = now
        lease.state = "RELEASED"
        attempt.completed_at = now
        session.flush()
        return claim

    def retry_or_fail(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str,
                      error_code: str, retryable: bool, delay_seconds: int) -> str:
        session = self._session(transaction)
        job, lease, attempt = self._current(session, job_id, fencing_token, worker_ref)
        now = self._now(session)
        if job.lease_expires_at is None or job.lease_expires_at <= now or lease.lease_expires_at <= now:
            raise JobLeaseError("STALE_LEASE")
        lease.state = "RELEASED"
        attempt.completed_at = now
        attempt.error_code = error_code
        job.lease_expires_at = None
        if retryable and job.attempt_count < job.max_attempts:
            job.state = "RETRY_WAIT"
            job.available_at = now + timedelta(seconds=delay_seconds)
        else:
            job.state = "FAILED"
            job.completed_at = now
        session.flush()
        return job.state

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        return session

    @staticmethod
    def _now(session: Session):
        return session.execute(select(func.clock_timestamp())).scalar_one()

    @staticmethod
    def _claim(job: JobRow) -> ClaimedJob:
        return ClaimedJob(job.job_id, job.job_type, job.scope, job.project_id,
                          dict(job.payload_refs), job.trace_id,
                          job.fencing_token, job.attempt_count)

    @staticmethod
    def _lease(session: Session, job_id: uuid.UUID, token: int) -> JobLeaseRow:
        lease = session.execute(select(JobLeaseRow).where(
            JobLeaseRow.job_id == job_id,
            JobLeaseRow.fencing_token == token,
            JobLeaseRow.state == "ACTIVE",
        ).with_for_update(of=JobLeaseRow)).scalar_one_or_none()
        if lease is None:
            raise JobLeaseError("STALE_LEASE")
        return lease

    @staticmethod
    def _attempt(session: Session, job_id: uuid.UUID, token: int) -> JobAttemptRow:
        attempt = session.execute(select(JobAttemptRow).where(
            JobAttemptRow.job_id == job_id,
            JobAttemptRow.fencing_token == token,
        ).with_for_update(of=JobAttemptRow)).scalar_one_or_none()
        if attempt is None:
            raise JobLeaseError("INCONSISTENT_ATTEMPT")
        return attempt

    def _current(self, session: Session, job_id: uuid.UUID,
                 token: int, worker_ref: str) -> tuple[JobRow, JobLeaseRow, JobAttemptRow]:
        job = session.execute(select(JobRow).where(JobRow.job_id == job_id)
                              .with_for_update(of=JobRow)).scalar_one_or_none()
        if job is None or job.state != "RUNNING" or job.fencing_token != token:
            raise JobLeaseError("STALE_LEASE")
        lease = self._lease(session, job_id, token)
        if lease.worker_ref != worker_ref:
            raise JobLeaseError("STALE_LEASE")
        attempt = self._attempt(session, job_id, token)
        if attempt.worker_ref != worker_ref or attempt.completed_at is not None:
            raise JobLeaseError("STALE_LEASE")
        return job, lease, attempt
