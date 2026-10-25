"""Caller-UOW technical renewal; deliberately no authorization or own commit."""
from typing import Protocol
from uuid import UUID
from .lease import ClaimedJob, JobLeaseError
from .lease_checkpoint import JobLeaseCheckpoint, validate_checkpoint


class JobLeaseRenewalRepositoryPort(Protocol):
    def check_current(self, transaction: object, *, job_id: UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def heartbeat(self, transaction: object, *, job_id: UUID,
                  fencing_token: int, worker_ref: str, lease_seconds: int) -> None: ...


class JobLeaseRenewal:
    def __init__(self, *, repository: JobLeaseRenewalRepositoryPort):
        if repository is None:
            raise ValueError('Renewal repository required')
        self._repository = repository
        self._checkpoint = JobLeaseCheckpoint(repository=repository)

    def renew_current(self, transaction: object, *, job_id: UUID, fencing_token: int,
                      worker_ref: str, lease_seconds: int) -> ClaimedJob:
        """Caller MUST bind current Owner authority first and commit promptly after.

        Row locks live in caller transaction. Expired/cancelled/stale generations
        never revive. Any exception requires caller rollback; no file I/O here.
        """
        validate_checkpoint(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise JobLeaseError('INVALID_LEASE_DURATION')
        args = dict(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        before = self._checkpoint.check_current(transaction, **args)
        if self._repository.heartbeat(transaction, **args, lease_seconds=lease_seconds) is not None:
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        after = self._checkpoint.check_current(transaction, **args)
        if after != before:
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        return after
