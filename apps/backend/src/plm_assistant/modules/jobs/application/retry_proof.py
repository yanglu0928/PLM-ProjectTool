"""Immutable historical attempt receipt; NEVER a claim of current Job state."""
from dataclasses import dataclass
from datetime import datetime
from .lease import ClaimedJob,JobLeaseError


@dataclass(frozen=True,slots=True)
class RetryTransitionProof:
    claim: ClaimedJob
    state: str
    started_at: datetime
    completed_at: datetime
    available_at: datetime|None

    def __post_init__(self):
        if (type(self.claim) is not ClaimedJob or type(self.state) is not str or self.state not in {'RETRY_WAIT','FAILED'}
                or any(type(v) is not datetime or v.tzinfo is None or v.utcoffset() is None for v in (self.started_at,self.completed_at))
                or self.started_at>self.completed_at):raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        if self.state=='RETRY_WAIT':
            if (type(self.available_at) is not datetime or self.available_at.tzinfo is None or self.available_at.utcoffset() is None
                    or self.available_at<=self.completed_at):raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        elif self.available_at is not None:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
