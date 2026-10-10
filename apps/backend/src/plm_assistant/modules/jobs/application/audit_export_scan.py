"""Bounded owned technical cursor: neither authorization nor claim evidence."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from .audit_export_claim import AuditExportClaimCandidate
from .lease import JobLeaseError


@dataclass(frozen=True,slots=True)
class AuditExportScanCursor:
    priority: int
    available_at: datetime
    job_id: UUID

    def __post_init__(self):
        if (type(self.priority) is not int or not -(2**31)<=self.priority<2**31
                or type(self.available_at) is not datetime or self.available_at.tzinfo is None or self.available_at.utcoffset() is None
                or type(self.job_id) is not UUID or not self.job_id.int):raise JobLeaseError('VALIDATION_FAILED')


@dataclass(frozen=True,slots=True)
class AuditExportScanReservation:
    cursor: AuditExportScanCursor
    candidate: AuditExportClaimCandidate|None
    reason_code: str|None=None

    def __post_init__(self):
        if type(self.cursor) is not AuditExportScanCursor:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        self.cursor.__post_init__()
        if self.candidate is None:
            if type(self.reason_code) is not str or self.reason_code!='INVALID_EXPORT_REF':raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        else:
            if type(self.candidate) is not AuditExportClaimCandidate or self.reason_code is not None:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            self.candidate.__post_init__()
            if self.candidate.job_id!=self.cursor.job_id:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
