"""Authorized keyset page of immutable PlanVersion summaries."""

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


class PlanVersionListError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PlanVersionListQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanVersionSummary:
    plan_version_id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlanVersionListPage:
    items: tuple[PlanVersionSummary, ...]
    next_version_no: int | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     plan_id: uuid.UUID, after_version_no: int | None,
                     limit: int) -> PlanVersionListPage | None: ...


class PlanVersionListService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("PlanVersion list dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_current(self, query: PlanVersionListQuery, *, plan_id: uuid.UUID,
                     after_version_no: int | None = None,
                     limit: int = 50) -> PlanVersionListPage:
        if (type(query) is not PlanVersionListQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or not self._id(query.trace_id) or not self._id(query.project_id)
                or not self._id(plan_id)
                or (after_version_no is not None and (
                    type(after_version_no) is not int or after_version_no < 1))
                or type(limit) is not int or not 1 <= limit <= 200):
            raise PlanVersionListError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise PlanVersionListError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise PlanVersionListError("AUTH_ACCESS_DENIED")
                authorization = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="PLAN_VERSION_LIST")
                if (authorization.user_id != actor
                        or authorization.project_id != query.project_id
                        or authorization.operation != "PLAN_VERSION_LIST"):
                    raise PlanVersionListError("RESOURCE_NOT_FOUND")
                page = self._repository.list_current(
                    tx, project_id=query.project_id, plan_id=plan_id,
                    after_version_no=after_version_no, limit=limit)
                if page is None:
                    raise PlanVersionListError("RESOURCE_NOT_FOUND")
                if (type(page) is not PlanVersionListPage
                        or type(page.items) is not tuple or len(page.items) > limit
                        or type(page.has_more) is not bool
                        or (page.has_more and (not page.items
                            or page.next_version_no != page.items[-1].version_no))
                        or (not page.has_more and page.next_version_no is not None)):
                    raise PlanVersionListError()
                previous = after_version_no or 2**63
                for item in page.items:
                    if (type(item) is not PlanVersionSummary
                            or item.plan_id != plan_id or item.project_id != query.project_id
                            or not self._id(item.plan_version_id)
                            or not self._id(item.created_by)
                            or type(item.version_no) is not int
                            or not 1 <= item.version_no < previous
                            or item.version_state not in (
                                "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                                "SUPERSEDED", "RESTRICTED")
                            or any(value is not None and not self._id(value) for value in (
                                item.supersedes_version_ref, item.review_ref,
                                item.review_round_ref))
                            or type(item.created_at) is not datetime
                            or item.created_at.tzinfo is None
                            or item.created_at.utcoffset() is None):
                        raise PlanVersionListError()
                    previous = item.version_no
                return page
        except PlanVersionListError:
            raise
        except ProjectAuthorizationError as error:
            raise PlanVersionListError(error.code) from None
        except RuntimeLicenseError:
            raise PlanVersionListError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanVersionListError() from None

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
