"""Short caller-transaction lease checkpoint; no renewal, completion or authorization."""
from typing import Protocol
from uuid import UUID
from .lease import ClaimedJob, JobLeaseError, JobLeaseService


def validate_checkpoint(*, job_id, fencing_token, worker_ref):
    if type(job_id) is not UUID or not job_id.int:
        raise JobLeaseError("INVALID_JOB_ID")
    if type(fencing_token) is not int or not 1 <= fencing_token <= 2**63-1:
        raise JobLeaseError("INVALID_FENCING_TOKEN")
    if type(worker_ref) is not str:
        raise JobLeaseError("INVALID_WORKER")
    JobLeaseService._validate_worker(worker_ref)


class JobLeaseCheckpointRepositoryPort(Protocol):
    def check_current(self, transaction: object, *, job_id: UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class JobLeaseCheckpoint:
    def __init__(self, *, repository: JobLeaseCheckpointRepositoryPort):
        if repository is None:
            raise ValueError("checkpoint repository required")
        self._repository = repository

    def check_current(self, transaction: object, *, job_id: UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob:
        """Keep actual facts locked until caller ends UOW; result is not a reusable permit."""
        validate_checkpoint(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        result = self._repository.check_current(transaction, job_id=job_id,
            fencing_token=fencing_token, worker_ref=worker_ref)
        if (type(result) is not ClaimedJob or result.job_id != job_id
                or type(result.fencing_token) is not int or result.fencing_token != fencing_token
                or type(result.attempt_no) is not int or result.attempt_no < 1):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        return result
