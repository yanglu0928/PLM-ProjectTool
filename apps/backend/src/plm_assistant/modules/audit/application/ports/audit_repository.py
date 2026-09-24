"""Internal append-only persistence Port."""

from __future__ import annotations

import uuid
from typing import Protocol

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft


class AuditRepositoryPort(Protocol):
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        """Insert within caller-owned transaction; never commit or update."""
