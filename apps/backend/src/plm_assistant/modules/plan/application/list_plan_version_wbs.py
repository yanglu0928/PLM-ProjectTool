"""Authorized keyset page of immutable WBS items for one fixed PlanVersion."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class PlanVersionWbsReadError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PlanVersionWbsReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanVersionWbsItemView:
    wbs_item_id: uuid.UUID
    ordinal: int
    data: dict[str, object] = field(repr=False)


@dataclass(frozen=True, slots=True)
class PlanVersionWbsPage:
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID
    project_id: uuid.UUID
    items: tuple[PlanVersionWbsItemView, ...]
    next_ordinal: int | None
    next_wbs_item_id: uuid.UUID | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     plan_id: uuid.UUID, plan_version_id: uuid.UUID,
                     after_ordinal: int | None, after_wbs_item_id: uuid.UUID | None,
                     limit: int) -> PlanVersionWbsPage | None: ...


class PlanVersionWbsReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("PlanVersion WBS read dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_current(self, query: PlanVersionWbsReadQuery, *, plan_id: uuid.UUID,
                     plan_version_id: uuid.UUID,
                     after_ordinal: int | None = None,
                     after_wbs_item_id: uuid.UUID | None = None,
                     limit: int = 50) -> PlanVersionWbsPage:
        self._validate_query(query)
        if (not self._id(plan_id) or not self._id(plan_version_id)
                or ((after_ordinal is None) != (after_wbs_item_id is None))
                or (after_ordinal is not None and (
                    type(after_ordinal) is not int or after_ordinal < 1
                    or not self._id(after_wbs_item_id)))
                or type(limit) is not int or not 1 <= limit <= 200):
            raise PlanVersionWbsReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise PlanVersionWbsReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise PlanVersionWbsReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="PLAN_VERSION_WBS_LIST")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "PLAN_VERSION_WBS_LIST"):
                    raise PlanVersionWbsReadError("RESOURCE_NOT_FOUND")
                page = self._repository.list_current(
                    tx, project_id=query.project_id, plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    after_ordinal=after_ordinal,
                    after_wbs_item_id=after_wbs_item_id, limit=limit)
                if page is None:
                    raise PlanVersionWbsReadError("RESOURCE_NOT_FOUND")
                if (type(page) is not PlanVersionWbsPage
                        or page.plan_id != plan_id
                        or page.plan_version_id != plan_version_id
                        or page.project_id != query.project_id
                        or type(page.items) is not tuple or len(page.items) > limit
                        or type(page.has_more) is not bool
                        or (page.has_more and (not page.items
                            or page.next_ordinal != page.items[-1].ordinal
                            or page.next_wbs_item_id != page.items[-1].wbs_item_id))
                        or (not page.has_more and (page.next_ordinal is not None
                            or page.next_wbs_item_id is not None))
                        or any(type(item) is not PlanVersionWbsItemView
                               or not self._id(item.wbs_item_id)
                               or type(item.ordinal) is not int or item.ordinal < 1
                               or type(item.data) is not dict
                               for item in page.items)):
                    raise PlanVersionWbsReadError()
                return page
        except PlanVersionWbsReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PlanVersionWbsReadError(error.code) from None
        except RuntimeLicenseError:
            raise PlanVersionWbsReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanVersionWbsReadError() from None

    @classmethod
    def _validate_query(cls, query: PlanVersionWbsReadQuery) -> None:
        if (type(query) is not PlanVersionWbsReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not cls._id(query.trace_id) or not cls._id(query.project_id)):
            raise PlanVersionWbsReadError("VALIDATION_FAILED")

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
