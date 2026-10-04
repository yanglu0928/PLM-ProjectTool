"""Read-only scan contracts for expired Parser cancellations; never authority."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from .lease import JobLeaseError
from .lease_checkpoint import validate_checkpoint


@dataclass(frozen=True, slots=True)
class ExpiredParserCancelCursor:
    expired_at: datetime
    job_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.expired_at) is not datetime or self.expired_at.tzinfo is None
                or self.expired_at.utcoffset() is None
                or type(self.job_id) is not uuid.UUID or self.job_id.int == 0):
            raise JobLeaseError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class ExpiredParserCancelCandidate:
    cursor: ExpiredParserCancelCursor
    fencing_token: int
    worker_ref: str

    def __post_init__(self) -> None:
        if type(self.cursor) is not ExpiredParserCancelCursor:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        self.cursor.__post_init__()
        validate_checkpoint(job_id=self.cursor.job_id,
                            fencing_token=self.fencing_token,
                            worker_ref=self.worker_ref)


class ExpiredParserCancelCandidates:
    def __init__(self, *, repository):
        if repository is None:
            raise ValueError("Parser scan repository required")
        self._repository = repository

    def scan_next(self, tx, *, after: ExpiredParserCancelCursor | None = None
                  ) -> ExpiredParserCancelCandidate | None:
        if after is not None:
            if type(after) is not ExpiredParserCancelCursor:
                raise JobLeaseError("VALIDATION_FAILED")
            after.__post_init__()
        try:
            candidate = self._repository.scan_next(tx, after=after)
            if candidate is not None:
                if type(candidate) is not ExpiredParserCancelCandidate:
                    raise JobLeaseError("JOB_STORE_UNAVAILABLE")
                candidate.__post_init__()
            return candidate
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
