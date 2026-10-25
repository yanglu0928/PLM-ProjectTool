"""Authorized read of one immutable, fixed PlanVersion snapshot."""

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


class PlanVersionReadError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PlanVersionReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanVersionSnapshotView:
    plan_version_id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    created_by: uuid.UUID
    created_at: datetime
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    snapshot: dict[str, object] = field(repr=False)


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    plan_id: uuid.UUID, plan_version_id: uuid.UUID
                    ) -> PlanVersionSnapshotView | None: ...


class PlanVersionReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("PlanVersion read dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_current(self, query: PlanVersionReadQuery, *, plan_id: uuid.UUID,
                    plan_version_id: uuid.UUID) -> PlanVersionSnapshotView:
        self._validate_query(query)
        if not self._id(plan_id) or not self._id(plan_version_id):
            raise PlanVersionReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise PlanVersionReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise PlanVersionReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="PLAN_VERSION_GET")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "PLAN_VERSION_GET"):
                    raise PlanVersionReadError("RESOURCE_NOT_FOUND")
                view = self._repository.get_current(
                    tx, project_id=query.project_id, plan_id=plan_id,
                    plan_version_id=plan_version_id)
                if view is None:
                    raise PlanVersionReadError("RESOURCE_NOT_FOUND")
                if (type(view) is not PlanVersionSnapshotView
                        or view.plan_id != plan_id
                        or view.plan_version_id != plan_version_id
                        or view.project_id != query.project_id
                        or not self._id(view.created_by)
                        or type(view.version_no) is not int or view.version_no < 1
                        or view.version_state not in {
                            "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                            "SUPERSEDED", "RESTRICTED",
                        }
                        or type(view.created_at) is not datetime
                        or view.created_at.tzinfo is None
                        or view.created_at.utcoffset() is None
                        or any(value is not None and not self._id(value)
                               for value in (view.supersedes_version_ref,
                                             view.review_ref,
                                             view.review_round_ref))
                        or type(view.snapshot) is not dict):
                    raise PlanVersionReadError()
                return view
        except PlanVersionReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PlanVersionReadError(error.code) from None
        except RuntimeLicenseError:
            raise PlanVersionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanVersionReadError() from None

    @classmethod
    def _validate_query(cls, query: PlanVersionReadQuery) -> None:
        if (type(query) is not PlanVersionReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not cls._id(query.trace_id) or not cls._id(query.project_id)):
            raise PlanVersionReadError("VALIDATION_FAILED")

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
