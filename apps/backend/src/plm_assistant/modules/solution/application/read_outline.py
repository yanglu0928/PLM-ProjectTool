"""Authorized read of a SolutionOutline identity and approved pointer."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class OutlineReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OutlineCurrentView:
    solution_outline_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    outline_state: str
    current_approved_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class OutlineSummaryView:
    solution_outline_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    outline_state: str
    current_approved_version_ref: uuid.UUID | None
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class OutlineListPage:
    items: tuple[OutlineSummaryView, ...]
    next_after_outline_id: uuid.UUID | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    outline_id: uuid.UUID) -> OutlineCurrentView | None: ...

    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     after_outline_id: uuid.UUID | None,
                     limit: int) -> OutlineListPage: ...


class OutlineReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Outline read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_current(self, query: OutlineReadQuery,
                    outline_id: uuid.UUID) -> OutlineCurrentView:
        if (type(query) is not OutlineReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not self._id(query.trace_id)
                or not self._id(query.project_id)):
            raise OutlineReadError("VALIDATION_FAILED")
        if not self._id(outline_id):
            raise OutlineReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise OutlineReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise OutlineReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SOL_OUTLINE_GET")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "SOL_OUTLINE_GET"):
                    raise OutlineReadError("RESOURCE_NOT_FOUND")
                view = self._repository.get_current(
                    tx, project_id=query.project_id, outline_id=outline_id)
                if view is None:
                    raise OutlineReadError("RESOURCE_NOT_FOUND")
                if (type(view) is not OutlineCurrentView
                        or view.solution_outline_id != outline_id
                        or view.project_id != query.project_id
                        or type(view.name) is not str or not view.name
                        or view.outline_state not in ("ACTIVE", "ARCHIVED")
                        or (view.current_approved_version_ref is not None
                            and not self._id(view.current_approved_version_ref))
                        or not self._id(view.created_by)
                        or type(view.created_at) is not datetime
                        or view.created_at.tzinfo is None
                        or view.created_at.utcoffset() is None
                        or type(view.etag) is not str
                        or re.fullmatch(r'"v(0|[1-9][0-9]*)"', view.etag,
                                        flags=re.ASCII) is None):
                    raise OutlineReadError()
                return view
        except OutlineReadError:
            raise
        except ProjectAuthorizationError as error:
            raise OutlineReadError(error.code) from None
        except RuntimeLicenseError:
            raise OutlineReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutlineReadError() from None

    def list_current(self, query: OutlineReadQuery, *,
                     after_outline_id: uuid.UUID | None = None,
                     limit: int = 50) -> OutlineListPage:
        if (type(query) is not OutlineReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not self._id(query.trace_id)
                or not self._id(query.project_id)
                or (after_outline_id is not None and not self._id(after_outline_id))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise OutlineReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise OutlineReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise OutlineReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SOL_OUTLINE_LIST")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "SOL_OUTLINE_LIST"):
                    raise OutlineReadError("RESOURCE_NOT_FOUND")
                page = self._repository.list_current(
                    tx, project_id=query.project_id,
                    after_outline_id=after_outline_id, limit=limit)
                self._validate_page(page, query.project_id, after_outline_id, limit)
                return page
        except OutlineReadError:
            raise
        except ProjectAuthorizationError as error:
            raise OutlineReadError(error.code) from None
        except RuntimeLicenseError:
            raise OutlineReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutlineReadError() from None

    @classmethod
    def _validate_page(cls, page: OutlineListPage, project_id: uuid.UUID,
                       after: uuid.UUID | None, limit: int) -> None:
        if (type(page) is not OutlineListPage
                or type(page.items) is not tuple
                or len(page.items) > limit
                or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_after_outline_id
                    != page.items[-1].solution_outline_id))
                or (not page.has_more and page.next_after_outline_id is not None)):
            raise OutlineReadError()
        previous = after
        for item in page.items:
            if (type(item) is not OutlineSummaryView
                    or not cls._id(item.solution_outline_id)
                    or (previous is not None
                        and item.solution_outline_id.int <= previous.int)
                    or item.project_id != project_id
                    or type(item.name) is not str or not item.name
                    or item.outline_state not in ("ACTIVE", "ARCHIVED")
                    or (item.current_approved_version_ref is not None
                        and not cls._id(item.current_approved_version_ref))
                    or type(item.created_at) is not datetime
                    or item.created_at.tzinfo is None
                    or item.created_at.utcoffset() is None
                    or type(item.etag) is not str
                    or re.fullmatch(r'"v(0|[1-9][0-9]*)"', item.etag,
                                    flags=re.ASCII) is None):
                raise OutlineReadError()
            previous = item.solution_outline_id

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
