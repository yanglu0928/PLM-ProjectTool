"""Scoped Project Department history pages for current project members."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class ProjectDepartmentReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProjectDepartmentListQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    after_department_id: uuid.UUID | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class DepartmentFacts:
    department_id: uuid.UUID
    project_id: uuid.UUID
    code: str
    name: str
    state: str
    created_at: datetime
    lock_version: int


@dataclass(frozen=True, slots=True)
class DepartmentView:
    department_id: uuid.UUID
    code: str
    name: str
    state: str
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class DepartmentPage:
    items: tuple[DepartmentView, ...]
    next_after_department_id: uuid.UUID | None
    has_more: bool


class ProjectDepartmentReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectDepartmentReadRepositoryPort(Protocol):
    def list_page(self, transaction: object, *, project_id: uuid.UUID,
                  after_department_id: uuid.UUID | None,
                  limit: int) -> tuple[DepartmentFacts, ...]: ...


class ProjectDepartmentReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectDepartmentReadAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectDepartmentReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository)):
            raise ValueError("Project Department read dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_page(self, query: ProjectDepartmentListQuery) -> DepartmentPage:
        if (type(query) is not ProjectDepartmentListQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0
                or (query.after_department_id is not None and (
                    type(query.after_department_id) is not uuid.UUID
                    or query.after_department_id.int == 0))
                or type(query.limit) is not int or not 1 <= query.limit <= 200):
            raise ProjectDepartmentReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                    raise ProjectDepartmentReadError("PROJECT_UNAVAILABLE")
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise ProjectDepartmentReadError("AUTH_ACCESS_DENIED")
                try:
                    self._authorization.require_in_transaction(
                        tx, user_id=actor, project_id=query.project_id,
                        operation="PROJECT_DEPARTMENT_LIST",
                    )
                except ProjectAuthorizationError as exc:
                    raise ProjectDepartmentReadError(exc.code) from None
                facts = self._repository.list_page(
                    tx, project_id=query.project_id,
                    after_department_id=query.after_department_id,
                    limit=query.limit + 1,
                )
                if (type(facts) is not tuple or len(facts) > query.limit + 1
                        or any(type(item) is not DepartmentFacts
                               or item.project_id != query.project_id for item in facts)):
                    raise ProjectDepartmentReadError("PROJECT_UNAVAILABLE")
                has_more = len(facts) > query.limit
                visible = facts[:query.limit]
                return DepartmentPage(
                    tuple(DepartmentView(
                        item.department_id, item.code, item.name, item.state,
                        item.created_at, f'"v{item.lock_version}"',
                    ) for item in visible),
                    visible[-1].department_id if has_more else None,
                    has_more,
                )
        except ProjectDepartmentReadError:
            raise
        except RuntimeLicenseError:
            raise ProjectDepartmentReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ProjectDepartmentReadError("PROJECT_UNAVAILABLE") from None
