"""Scoped ProjectMember history pages for authorized management roles."""

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


class ProjectMemberReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProjectMemberListQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    after_member_id: uuid.UUID | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class MemberFacts:
    member_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    department_id: uuid.UUID
    department_name: str
    state: str
    effective_at: datetime
    ended_at: datetime | None
    lock_version: int


@dataclass(frozen=True, slots=True)
class ProjectMemberView:
    member_id: uuid.UUID
    user_id: uuid.UUID
    user_display_name: str
    role: str
    department_id: uuid.UUID
    department_name: str
    state: str
    effective_at: datetime
    ended_at: datetime | None
    etag: str


@dataclass(frozen=True, slots=True)
class ProjectMemberPage:
    items: tuple[ProjectMemberView, ...]
    next_after_member_id: uuid.UUID | None
    has_more: bool


class ProjectMemberReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...
    def display_names(self, transaction: object,
                      user_ids: tuple[uuid.UUID, ...]) -> dict[uuid.UUID, str]: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectMemberRepositoryPort(Protocol):
    def list_page(self, transaction: object, *, project_id: uuid.UUID,
                  after_member_id: uuid.UUID | None, limit: int) -> tuple[MemberFacts, ...]: ...


class ProjectMemberReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectMemberReadAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectMemberRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository)):
            raise ValueError("ProjectMember read dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_page(self, query: ProjectMemberListQuery) -> ProjectMemberPage:
        if (type(query) is not ProjectMemberListQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0
                or (query.after_member_id is not None and (
                    type(query.after_member_id) is not uuid.UUID or query.after_member_id.int == 0))
                or type(query.limit) is not int or not 1 <= query.limit <= 200):
            raise ProjectMemberReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                    raise ProjectMemberReadError("PROJECT_UNAVAILABLE")
                user_id = self._access.authenticated_user(
                    tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
                )
                if type(user_id) is not uuid.UUID or user_id.int == 0:
                    raise ProjectMemberReadError("AUTH_ACCESS_DENIED")
                try:
                    self._authorization.require_in_transaction(
                        tx, user_id=user_id, project_id=query.project_id,
                        operation="PROJECT_MEMBER_LIST",
                    )
                except ProjectAuthorizationError as exc:
                    raise ProjectMemberReadError(exc.code) from None
                facts = self._repository.list_page(
                    tx, project_id=query.project_id,
                    after_member_id=query.after_member_id, limit=query.limit + 1,
                )
                if (type(facts) is not tuple or len(facts) > query.limit + 1
                        or any(type(item) is not MemberFacts
                               or item.project_id != query.project_id for item in facts)):
                    raise ProjectMemberReadError("PROJECT_UNAVAILABLE")
                has_more = len(facts) > query.limit
                visible = facts[:query.limit]
                names = self._access.display_names(tx, tuple(item.user_id for item in visible))
                if (type(names) is not dict or any(type(names.get(item.user_id)) is not str
                                                for item in visible)):
                    raise ProjectMemberReadError("PROJECT_UNAVAILABLE")
                items = tuple(ProjectMemberView(
                    item.member_id, item.user_id, names[item.user_id], item.role,
                    item.department_id, item.department_name, item.state,
                    item.effective_at, item.ended_at, f'"v{item.lock_version}"',
                ) for item in visible)
                return ProjectMemberPage(
                    items, visible[-1].member_id if has_more else None, has_more,
                )
        except ProjectMemberReadError:
            raise
        except RuntimeLicenseError:
            raise ProjectMemberReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ProjectMemberReadError("PROJECT_UNAVAILABLE") from None
