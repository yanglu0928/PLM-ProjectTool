"""Trusted Owner storage results, never current authority or lease proof."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class AuditCaptureError(RuntimeError):
    def __init__(self, reason="INVALID_SOURCE"):
        if reason not in {"INVALID_REQUEST", "NOT_FOUND", "BINDING_MISMATCH", "INVALID_SOURCE", "LIMIT_EXCEEDED"}:
            raise ValueError("invalid Audit capture error")
        self.reason = reason
        super().__init__("Audit capture unavailable")


@dataclass(frozen=True, slots=True)
class CapturedAuditExport:
    export_id: UUID
    actor_id: UUID
    scope: str
    project_id: UUID | None
    requested_at: datetime
    captured_at: datetime
    member_count: int
    membership_hash: str
    membership_version: str
    intent_hash: str
    policy_version: str
    projection_version: str
    format_version: str
