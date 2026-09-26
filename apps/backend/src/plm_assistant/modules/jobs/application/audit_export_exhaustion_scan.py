"""An expired exhausted candidate is only a hint, never mutation authority."""
from dataclasses import dataclass
from uuid import UUID
from .lease import JobLeaseError
from .lease_checkpoint import validate_checkpoint


@dataclass(frozen=True,slots=True)
class AuditExportExhaustionCandidate:
    job_id: UUID
    export_id: UUID
    fencing_token: int
    worker_ref: str

    def __post_init__(self):
        if type(self.export_id) is not UUID or not self.export_id.int:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        validate_checkpoint(job_id=self.job_id,fencing_token=self.fencing_token,worker_ref=self.worker_ref)


class AuditExportExhaustionCandidates:
    def __init__(self,*,repository):
        if repository is None:raise ValueError('Owned candidate repository required')
        self._repo=repository

    def peek_next(self,tx):
        try:
            value=self._repo.peek_next(tx)
            if value is not None:
                if type(value) is not AuditExportExhaustionCandidate:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
                value.__post_init__()
            return value
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
