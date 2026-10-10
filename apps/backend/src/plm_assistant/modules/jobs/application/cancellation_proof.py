"""Internal owned terminal cancellation proof, NEVER authority or commit inference."""
from dataclasses import dataclass
from datetime import datetime
from .lease import ClaimedJob
from .audit_export_cancel import AuditExportCancellationError


@dataclass(frozen=True,slots=True)
class CancelledJobProof:
    claim: ClaimedJob
    lease_state: str
    completed_at: datetime

    def __post_init__(self):
        if (type(self.claim) is not ClaimedJob or type(self.lease_state) is not str
                or self.lease_state not in {'RELEASED','EXPIRED'}
                or type(self.completed_at) is not datetime or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise AuditExportCancellationError('JOB_STORE_UNAVAILABLE')
