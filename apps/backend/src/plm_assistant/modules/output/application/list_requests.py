"""Authorized keyset pages for fixed OutputRequest snapshots."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.output.application.read_request import OutputRequestView
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class OutputRequestListError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutputRequestListQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    page_size: int = 50
    after_requested_at: datetime | None = None
    after_request_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class OutputRequestListPage:
    items: tuple[OutputRequestView, ...]
    next_requested_at: datetime | None
    next_request_id: uuid.UUID | None
    has_more: bool


class OutputRequestListAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class OutputRequestListLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class OutputRequestListRepositoryPort(Protocol):
    def list_page(self, transaction: object, *, project_id: uuid.UUID,
                  after_requested_at: datetime | None,
                  after_request_id: uuid.UUID | None,
                  limit: int) -> tuple[OutputRequestView, ...]: ...


class OutputRequestListService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: OutputRequestListAccessPort,
                 license_guard: OutputRequestListLicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: OutputRequestListRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in
               (unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("OutputRequest list dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_page(self, query: OutputRequestListQuery) -> OutputRequestListPage:
        if (type(query) is not OutputRequestListQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or type(query.project_id) is not uuid.UUID or not query.project_id.int
                or type(query.page_size) is not int or not 1 <= query.page_size <= 200
                or ((query.after_requested_at is None) != (query.after_request_id is None))
                or (query.after_requested_at is not None and (
                    not isinstance(query.after_requested_at, datetime)
                    or query.after_requested_at.tzinfo is None
                    or query.after_requested_at.utcoffset() is None
                    or type(query.after_request_id) is not uuid.UUID
                    or not query.after_request_id.int))):
            raise OutputRequestListError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if (not isinstance(now, datetime) or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise OutputRequestListError("SYSTEM_UNAVAILABLE")
                user_id = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(user_id) is not uuid.UUID or not user_id.int:
                    raise OutputRequestListError("AUTH_ACCESS_DENIED")
                try:
                    self._authorization.require_in_transaction(
                        transaction, user_id=user_id, project_id=query.project_id,
                        operation="OUTPUT_REQUEST_LIST",
                    )
                except ProjectAuthorizationError as exc:
                    raise OutputRequestListError(exc.code) from None
                rows = self._repository.list_page(
                    transaction, project_id=query.project_id,
                    after_requested_at=query.after_requested_at,
                    after_request_id=query.after_request_id,
                    limit=query.page_size + 1,
                )
                if (type(rows) is not tuple or len(rows) > query.page_size + 1
                        or any(type(row) is not OutputRequestView for row in rows)
                        or any(row.project_id != query.project_id for row in rows)):
                    raise OutputRequestListError("SYSTEM_UNAVAILABLE")
                has_more = len(rows) > query.page_size
                items = rows[:query.page_size]
                next_at = next_id = None
                if has_more and items:
                    next_at = items[-1].requested_at.astimezone(timezone.utc)
                    next_id = items[-1].output_request_id
                return OutputRequestListPage(items, next_at, next_id, has_more)
        except OutputRequestListError:
            raise
        except RuntimeLicenseError:
            raise OutputRequestListError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutputRequestListError("SYSTEM_UNAVAILABLE") from None
