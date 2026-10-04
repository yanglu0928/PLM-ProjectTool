"""Internal immutable technical proof; not business authority or an Audit event."""
from dataclasses import dataclass
from datetime import datetime
from .lease import ClaimedJob, JobLeaseError


@dataclass(frozen=True,slots=True)
class FailedJobProof:
    claim: ClaimedJob
    error_code: str
    completed_at: datetime

    def __post_init__(self):
        if (type(self.claim) is not ClaimedJob or type(self.error_code) is not str or not self.error_code
                or type(self.completed_at) is not datetime or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')
