"""Current authorized project Plan identity read; no approved version yet."""

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


class PlanReadError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PlanReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanCurrentView:
    plan_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    plan_state: str
    current_approved_version_ref: None
    created_by: uuid.UUID
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class PlanSummaryView:
    plan_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    plan_state: str
    current_approved_version_ref: None
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class PlanListPage:
    items: tuple[PlanSummaryView, ...]
    next_after_plan_id: uuid.UUID | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    plan_id: uuid.UUID) -> PlanCurrentView | None: ...

    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     after_plan_id: uuid.UUID | None, limit: int) -> PlanListPage: ...


class PlanReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort, authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Plan read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_current(self, query: PlanReadQuery, plan_id: uuid.UUID) -> PlanCurrentView:
        self._validate_query(query)
        if not self._id(plan_id):
            raise PlanReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, query)
                self._authorize(tx, actor, query.project_id, "PLAN_GET")
                view = self._repository.get_current(
                    tx, project_id=query.project_id, plan_id=plan_id)
                if view is None:
                    raise PlanReadError("RESOURCE_NOT_FOUND")
                if (type(view) is not PlanCurrentView
                        or view.plan_id != plan_id
                        or view.project_id != query.project_id
                        or not self._valid_fields(view)):
                    raise PlanReadError()
                return view
        except PlanReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PlanReadError(error.code) from None
        except RuntimeLicenseError:
            raise PlanReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanReadError() from None

    def list_current(self, query: PlanReadQuery, *,
                     after_plan_id: uuid.UUID | None = None,
                     limit: int = 50) -> PlanListPage:
        self._validate_query(query)
        if ((after_plan_id is not None and not self._id(after_plan_id))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise PlanReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, query)
                self._authorize(tx, actor, query.project_id, "PLAN_LIST")
                page = self._repository.list_current(
                    tx, project_id=query.project_id,
                    after_plan_id=after_plan_id, limit=limit)
                self._validate_page(page, query.project_id, after_plan_id, limit)
                return page
        except PlanReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PlanReadError(error.code) from None
        except RuntimeLicenseError:
            raise PlanReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanReadError() from None

    def _actor(self, tx: object, query: PlanReadQuery) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PlanReadError()
        actor = self._access.authenticated_user(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc))
        if not self._id(actor):
            raise PlanReadError("AUTH_ACCESS_DENIED")
        return actor

    def _authorize(self, tx: object, actor: uuid.UUID, project_id: uuid.UUID,
                   operation: str) -> None:
        authorized = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id, operation=operation)
        if (authorized.user_id != actor or authorized.project_id != project_id
                or authorized.operation != operation):
            raise PlanReadError("RESOURCE_NOT_FOUND")

    @classmethod
    def _validate_query(cls, query: PlanReadQuery) -> None:
        if (type(query) is not PlanReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not cls._id(query.trace_id) or not cls._id(query.project_id)):
            raise PlanReadError("VALIDATION_FAILED")

    @classmethod
    def _validate_page(cls, page: PlanListPage, project_id: uuid.UUID,
                       after: uuid.UUID | None, limit: int) -> None:
        if (type(page) is not PlanListPage or type(page.items) is not tuple
                or len(page.items) > limit or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_after_plan_id != page.items[-1].plan_id))
                or (not page.has_more and page.next_after_plan_id is not None)):
            raise PlanReadError()
        previous = after
        for item in page.items:
            if (type(item) is not PlanSummaryView or not cls._id(item.plan_id)
                    or (previous is not None and item.plan_id.int <= previous.int)
                    or item.project_id != project_id or not cls._valid_fields(item)):
                raise PlanReadError()
            previous = item.plan_id

    @classmethod
    def _valid_fields(cls, view: PlanCurrentView | PlanSummaryView) -> bool:
        return (
            type(view.name) is str and bool(view.name)
            and view.plan_state in ("ACTIVE", "ARCHIVED")
            and view.current_approved_version_ref is None
            and (type(view) is PlanSummaryView or cls._id(view.created_by))
            and type(view.created_at) is datetime
            and view.created_at.tzinfo is not None
            and view.created_at.utcoffset() is not None
            and type(view.etag) is str
            and re.fullmatch(r'"v(0|[1-9][0-9]*)"', view.etag,
                             flags=re.ASCII) is not None
        )

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
