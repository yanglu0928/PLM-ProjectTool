"""Current authorized Project list and detail reads; no HTTP route is mounted."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


class ProjectReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProjectReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ProjectView:
    project_id: uuid.UUID
    code: str
    name: str
    state: str
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class ProjectPage:
    items: tuple[ProjectView, ...]
    next_cursor: None = None
    has_more: bool = False


class ProjectReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectReadRepositoryPort(Protocol):
    def list_authorized(self, transaction: object, user_id: uuid.UUID) -> tuple[ProjectView, ...]: ...
    def get_authorized(self, transaction: object, user_id: uuid.UUID,
                       project_id: uuid.UUID) -> ProjectView | None: ...


class ProjectReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectReadAccessPort,
                 license_guard: LicenseGuardPort, repository: ProjectReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard, repository)):
            raise ValueError("Project read dependencies are required")
        self._uow, self._access, self._guard, self._repository = (
            unit_of_work, access, license_guard, repository,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list(self, query: ProjectReadQuery) -> ProjectPage:
        self._validate(query)
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                user_id = self._user(tx, query)
                items = self._repository.list_authorized(tx, user_id)
                if type(items) is not tuple or len(items) > 1 or any(type(item) is not ProjectView for item in items):
                    raise ProjectReadError("PROJECT_UNAVAILABLE")
                return ProjectPage(items)
        except ProjectReadError:
            raise
        except Exception:
            raise ProjectReadError("PROJECT_UNAVAILABLE") from None

    def get(self, query: ProjectReadQuery, project_id: uuid.UUID) -> ProjectView:
        self._validate(query)
        if type(project_id) is not uuid.UUID or project_id.int == 0:
            raise ProjectReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                user_id = self._user(tx, query)
                item = self._repository.get_authorized(tx, user_id, project_id)
                if type(item) is not ProjectView:
                    raise ProjectReadError("RESOURCE_NOT_FOUND")
                return item
        except ProjectReadError:
            raise
        except Exception:
            raise ProjectReadError("PROJECT_UNAVAILABLE") from None

    @staticmethod
    def _validate(query: ProjectReadQuery) -> None:
        if (type(query) is not ProjectReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise ProjectReadError("VALIDATION_FAILED")

    def _user(self, tx: object, query: ProjectReadQuery) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ProjectReadError("PROJECT_UNAVAILABLE")
        user_id = self._access.authenticated_user(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
        )
        if type(user_id) is not uuid.UUID or user_id.int == 0:
            raise ProjectReadError("AUTH_ACCESS_DENIED")
        return user_id
