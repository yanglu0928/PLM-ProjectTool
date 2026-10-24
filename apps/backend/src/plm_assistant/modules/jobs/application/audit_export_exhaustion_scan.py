"""An expired exhausted candidate is only a hint, never mutation authority."""
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True,slots=True)
class AuditExportExhaustionCursor:
    expired_at: datetime
    job_id: UUID

    def __post_init__(self):
        if (type(self.expired_at) is not datetime or self.expired_at.tzinfo is None or self.expired_at.utcoffset() is None
                or type(self.job_id) is not UUID or not self.job_id.int):raise JobLeaseError('VALIDATION_FAILED')


@dataclass(frozen=True,slots=True)
class AuditExportExhaustionScan:
    cursor: AuditExportExhaustionCursor
    candidate: AuditExportExhaustionCandidate|None
    reason_code: str|None=None

    def __post_init__(self):
        if type(self.cursor) is not AuditExportExhaustionCursor:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        self.cursor.__post_init__()
        if self.candidate is None:
            if type(self.reason_code) is not str or self.reason_code!='INVALID_EXPORT_REF':raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        else:
            if type(self.candidate) is not AuditExportExhaustionCandidate or self.reason_code is not None:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            self.candidate.__post_init__()
            if self.candidate.job_id!=self.cursor.job_id:raise JobLeaseError('JOB_STORE_UNAVAILABLE')


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

    def scan_next(self,tx,*,after=None):
        if after is not None:
            if type(after) is not AuditExportExhaustionCursor:raise JobLeaseError('VALIDATION_FAILED')
            after.__post_init__()
        try:
            value=self._repo.scan_next(tx,after=after)
            if value is not None:
                if type(value) is not AuditExportExhaustionScan:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
                value.__post_init__()
            return value
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
