"""Authorized, bounded AuditEvent reads; no public HTTP route yet."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_ROOT = re.compile(r"[A-Z]{2,3}-[0-9]{2}\Z", re.ASCII)


class AuditQueryError(ValueError):
    """Fixed safe error for malformed internal query parameters."""


class AuditAccessDenied(PermissionError):
    """No caller-specific or resource-specific details are exposed."""


@dataclass(frozen=True, slots=True)
class AuditPosition:
    occurred_at: datetime
    audit_event_id: uuid.UUID

    def __post_init__(self) -> None:
        if type(self.occurred_at) is not datetime or self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise AuditQueryError("audit position is invalid")
        if type(self.audit_event_id) is not uuid.UUID or self.audit_event_id.int == 0:
            raise AuditQueryError("audit position is invalid")


@dataclass(frozen=True, slots=True)
class AuditSearch:
    start_at: datetime
    end_at: datetime
    page_size: int = 50
    after: AuditPosition | None = None
    action: str | None = None
    outcome: str | None = None
    actor_id: uuid.UUID | None = None
    target_object_type: str | None = None
    target_object_id: uuid.UUID | None = None
    trace_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if any(type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None for value in (self.start_at, self.end_at)):
            raise AuditQueryError("audit time range is invalid")
        if not self.start_at < self.end_at or self.end_at - self.start_at > timedelta(days=31):
            raise AuditQueryError("audit time range is invalid")
        if type(self.page_size) is not int or not 1 <= self.page_size <= 200:
            raise AuditQueryError("audit page size is invalid")
        if self.after is not None and not isinstance(self.after, AuditPosition):
            raise AuditQueryError("audit position is invalid")
        if self.action is not None and (type(self.action) is not str or not _CODE.fullmatch(self.action)):
            raise AuditQueryError("audit action filter is invalid")
        if self.outcome is not None and self.outcome not in ("SUCCESS", "DENIED", "FAILED"):
            raise AuditQueryError("audit outcome filter is invalid")
        if self.target_object_type is not None and (type(self.target_object_type) is not str or not _ROOT.fullmatch(self.target_object_type)):
            raise AuditQueryError("audit target filter is invalid")
        for value in (self.actor_id, self.target_object_id, self.trace_id):
            if value is not None and (type(value) is not uuid.UUID or value.int == 0):
                raise AuditQueryError("audit identifier filter is invalid")


@dataclass(frozen=True, slots=True)
class AuditEventView:
    audit_event_id: uuid.UUID
    occurred_at: datetime
    trace_id: uuid.UUID
    event_scope: str
    target_project_id: uuid.UUID | None
    actor_type: str
    actor_id: uuid.UUID | None
    original_actor_id: uuid.UUID | None
    action: str
    outcome: str
    target_owner_module: str | None
    target_object_type: str | None
    target_object_id: uuid.UUID | None
    target_version_id: uuid.UUID | None
    reason_code: str | None
    before_state: str | None
    after_state: str | None


@dataclass(frozen=True, slots=True)
class AuditPage:
    items: tuple[AuditEventView, ...]
    next_position: AuditPosition | None
    has_more: bool


class AuditReadAccessPort(Protocol):
    def can_read_project(self, transaction: object, principal: object, project_id: uuid.UUID) -> bool: ...
    def can_read_deployment(self, transaction: object, principal: object) -> bool: ...


class AuditReadRepositoryPort(Protocol):
    def list_events(self, transaction: object, *, project_id: uuid.UUID | None, search: AuditSearch) -> AuditPage: ...
    def get_event(self, transaction: object, *, project_id: uuid.UUID | None, event_id: uuid.UUID) -> AuditEventView | None: ...


class AuditQueryService:
    def __init__(self, *, access: AuditReadAccessPort, repository: AuditReadRepositoryPort) -> None:
        if access is None or repository is None:
            raise ValueError("audit read dependencies are required")
        self._access = access
        self._repository = repository

    def list_project(self, transaction: object, principal: object, project_id: uuid.UUID, search: AuditSearch) -> AuditPage:
        self._require_project(transaction, principal, project_id)
        self._require_search(search)
        return self._repository.list_events(transaction, project_id=project_id, search=search)

    def get_project(self, transaction: object, principal: object, project_id: uuid.UUID, event_id: uuid.UUID) -> AuditEventView | None:
        self._require_project(transaction, principal, project_id)
        self._require_event_id(event_id)
        return self._repository.get_event(transaction, project_id=project_id, event_id=event_id)

    def list_deployment(self, transaction: object, principal: object, search: AuditSearch) -> AuditPage:
        self._require_deployment(transaction, principal)
        self._require_search(search)
        return self._repository.list_events(transaction, project_id=None, search=search)

    def get_deployment(self, transaction: object, principal: object, event_id: uuid.UUID) -> AuditEventView | None:
        self._require_deployment(transaction, principal)
        self._require_event_id(event_id)
        return self._repository.get_event(transaction, project_id=None, event_id=event_id)

    def _require_project(self, transaction: object, principal: object, project_id: uuid.UUID) -> None:
        if type(project_id) is not uuid.UUID or project_id.int == 0:
            raise AuditQueryError("audit project is invalid")
        if not self._access.can_read_project(transaction, principal, project_id):
            raise AuditAccessDenied("audit read denied")

    def _require_deployment(self, transaction: object, principal: object) -> None:
        if not self._access.can_read_deployment(transaction, principal):
            raise AuditAccessDenied("audit read denied")

    @staticmethod
    def _require_event_id(event_id: uuid.UUID) -> None:
        if type(event_id) is not uuid.UUID or event_id.int == 0:
            raise AuditQueryError("audit event is invalid")

    @staticmethod
    def _require_search(search: AuditSearch) -> None:
        if not isinstance(search, AuditSearch):
            raise AuditQueryError("audit search is invalid")
