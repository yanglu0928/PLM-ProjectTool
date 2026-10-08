"""Authorized PROJECT Reference current-version identity and fixed source read."""

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


class ReferenceReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReferenceReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ReferenceCurrentView:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    eligibility_state: str
    eligibility_reason: str | None
    version_no: int
    version_state: str
    source_project_class: str
    deidentification_class: str
    applicability: dict[str, object] = field(repr=False)
    document_version_ids: tuple[uuid.UUID, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    source_fingerprint: bytes = field(repr=False)
    content_fingerprint: bytes = field(repr=False)
    created_by: uuid.UUID
    created_at: datetime
    version_created_by: uuid.UUID
    version_created_at: datetime
    etag: str
    scope: str = "PROJECT"


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    reference_solution_id: uuid.UUID) -> ReferenceCurrentView | None: ...


class ReferenceReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Reference read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_current(self, query: ReferenceReadQuery,
                    reference_solution_id: uuid.UUID) -> ReferenceCurrentView:
        if (type(query) is not ReferenceReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not self._id(query.trace_id)
                or not self._id(query.project_id)):
            raise ReferenceReadError("VALIDATION_FAILED")
        if not self._id(reference_solution_id):
            raise ReferenceReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise ReferenceReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise ReferenceReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SOL_REFERENCE_GET")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "SOL_REFERENCE_GET"):
                    raise ReferenceReadError("RESOURCE_NOT_FOUND")
                view = self._repository.get_current(
                    tx, project_id=query.project_id,
                    reference_solution_id=reference_solution_id)
                if view is None:
                    raise ReferenceReadError("RESOURCE_NOT_FOUND")
                self._validate_view(view, query.project_id, reference_solution_id)
                return view
        except ReferenceReadError:
            raise
        except ProjectAuthorizationError as error:
            raise ReferenceReadError(error.code) from None
        except RuntimeLicenseError:
            raise ReferenceReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReferenceReadError() from None

    @classmethod
    def _validate_view(cls, view: ReferenceCurrentView | None,
                       project_id: uuid.UUID,
                       reference_solution_id: uuid.UUID) -> None:
        if (type(view) is not ReferenceCurrentView
                or view.reference_solution_id != reference_solution_id
                or not cls._id(view.reference_version_id)
                or view.project_id != project_id or view.scope != "PROJECT"
                or type(view.name) is not str or not view.name
                or view.eligibility_state not in (
                    "REFERENCE_ONLY", "ELIGIBLE", "RESTRICTED", "REVOKED")
                or (view.eligibility_reason is not None
                    and type(view.eligibility_reason) is not str)
                or type(view.version_no) is not int or view.version_no < 1
                or view.version_state != "DRAFT"
                or type(view.source_project_class) is not str
                or type(view.deidentification_class) is not str
                or type(view.applicability) is not dict
                or type(view.document_version_ids) is not tuple
                or not 1 <= len(view.document_version_ids) <= 100
                or type(view.evidence_ids) is not tuple
                or len(view.evidence_ids) > 500
                or any(not cls._id(value) for value in (
                    *view.document_version_ids, *view.evidence_ids))
                or len(set(view.document_version_ids)) != len(view.document_version_ids)
                or len(set(view.evidence_ids)) != len(view.evidence_ids)
                or type(view.source_fingerprint) is not bytes
                or len(view.source_fingerprint) != 32
                or type(view.content_fingerprint) is not bytes
                or len(view.content_fingerprint) != 32
                or not cls._id(view.created_by)
                or not cls._id(view.version_created_by)
                or not cls._time(view.created_at)
                or not cls._time(view.version_created_at)
                or type(view.etag) is not str
                or re.fullmatch(r'"v(0|[1-9][0-9]*)"', view.etag,
                                flags=re.ASCII) is None):
            raise ReferenceReadError()

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0

    @staticmethod
    def _time(value: object) -> bool:
        return (type(value) is datetime and value.tzinfo is not None
                and value.utcoffset() is not None)
