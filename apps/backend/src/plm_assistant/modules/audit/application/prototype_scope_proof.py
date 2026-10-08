"""Audit-owned user-action witness for a Prototype NOT_REQUIRED decision."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PrototypeScopeDecisionAuditProof:
    audit_event_id: uuid.UUID
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    actor_id: uuid.UUID
    occurred_at: datetime

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.audit_event_id, self.project_id, self.prototype_id,
                self.actor_id))
                or type(self.occurred_at) is not datetime
                or self.occurred_at.tzinfo is None
                or self.occurred_at.utcoffset() != timedelta(0)):
            raise ValueError("invalid Prototype decision Audit proof")


class PrototypeScopeDecisionAuditProofPort(Protocol):
    def prove_user_action(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID, confirmed_by: uuid.UUID,
        decided_at: datetime,
    ) -> PrototypeScopeDecisionAuditProof | None: ...
