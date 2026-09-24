"""Only supported application entry for appending AuditEvents."""

from __future__ import annotations

import uuid

from plm_assistant.modules.audit.application.ports.audit_repository import AuditRepositoryPort
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft


class AuditService:
    def __init__(self, repository: AuditRepositoryPort) -> None:
        if repository is None:
            raise ValueError("audit repository is required")
        self._repository = repository

    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        if not isinstance(event, AuditEventDraft):
            raise TypeError("audit event draft is required")
        if transaction is None:
            raise ValueError("active audit transaction is required")
        return self._repository.append(transaction, event)
