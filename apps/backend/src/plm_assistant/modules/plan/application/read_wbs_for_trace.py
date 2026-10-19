"""Authorize one immutable WBS identity for a caller's Trace transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class PlanWbsTraceReadError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PlanWbsTraceQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanWbsTraceIdentity:
    wbs_item_id: uuid.UUID
    plan_version_id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    version_state: str
    plan_state: str


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get_fixed(self, transaction: object, *, project_id: uuid.UUID,
                  wbs_item_id: uuid.UUID,
                  plan_version_id: uuid.UUID) -> PlanWbsTraceIdentity | None: ...


class PlanWbsTraceReadService:
    def __init__(self, *, access: AccessPort, license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                access, license_guard, authorization, repository)):
            raise ValueError("WBS Trace read dependencies required")
        self._access, self._guard = access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_for_trace(self, transaction: object, query: PlanWbsTraceQuery, *,
                      wbs_item_id: uuid.UUID,
                      plan_version_id: uuid.UUID) -> PlanWbsTraceIdentity:
        if (transaction is None or type(query) is not PlanWbsTraceQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or not all(self._id(value) for value in (
                    query.trace_id, query.project_id, wbs_item_id, plan_version_id))):
            raise PlanWbsTraceReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            now = self._clock()
            if (type(now) is not datetime or now.tzinfo is None
                    or now.utcoffset() is None):
                raise PlanWbsTraceReadError()
            actor = self._access.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc))
            if not self._id(actor):
                raise PlanWbsTraceReadError("AUTH_ACCESS_DENIED")
            authorized = self._authorization.require_in_transaction(
                transaction, user_id=actor, project_id=query.project_id,
                operation="PLAN_VERSION_WBS_LIST")
            if (authorized.user_id != actor
                    or authorized.project_id != query.project_id
                    or authorized.operation != "PLAN_VERSION_WBS_LIST"):
                raise PlanWbsTraceReadError("RESOURCE_NOT_FOUND")
            result = self._repository.get_fixed(
                transaction, project_id=query.project_id,
                wbs_item_id=wbs_item_id, plan_version_id=plan_version_id)
            if result is None:
                raise PlanWbsTraceReadError("RESOURCE_NOT_FOUND")
            if (type(result) is not PlanWbsTraceIdentity
                    or result.wbs_item_id != wbs_item_id
                    or result.plan_version_id != plan_version_id
                    or result.project_id != query.project_id
                    or not self._id(result.plan_id)
                    or result.plan_state not in ("ACTIVE", "ARCHIVED")
                    or result.version_state not in (
                        "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED")):
                raise PlanWbsTraceReadError("RESOURCE_NOT_FOUND")
            return result
        except PlanWbsTraceReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PlanWbsTraceReadError(error.code) from None
        except RuntimeLicenseError:
            raise PlanWbsTraceReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanWbsTraceReadError() from None

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
