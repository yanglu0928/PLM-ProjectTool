"""Authorized, fixed-version OutputRequest detail reads; no HTTP or execution."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class OutputRequestReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutputRequestReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OutputRequestView:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    output_type: str
    template_version_ref: uuid.UUID
    source_version_refs: tuple[uuid.UUID, ...]
    output_policy_ref: str
    plugin_operation: str
    context_snapshot_ref: uuid.UUID
    context_fingerprint: bytes = field(repr=False)
    request_state: str
    job_ref: uuid.UUID | None
    execution_ref: uuid.UUID | None
    generation_no: int
    requested_at: datetime
    completed_at: datetime | None
    lock_version: int


class OutputRequestReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class OutputRequestProjectReadPort(Protocol):
    def get_authorized(self, transaction: object, user_id: uuid.UUID,
                       project_id: uuid.UUID) -> object | None: ...


class OutputRequestReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class OutputRequestReadRepositoryPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            output_request_id: uuid.UUID) -> OutputRequestView | None: ...


class OutputRequestReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: OutputRequestReadAccessPort,
                 projects: OutputRequestProjectReadPort,
                 license_guard: OutputRequestReadLicensePort,
                 repository: OutputRequestReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in
               (unit_of_work, access, projects, license_guard, repository)):
            raise ValueError("OutputRequest read dependencies are required")
        self._uow, self._access, self._projects, self._guard, self._repository = (
            unit_of_work, access, projects, license_guard, repository,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: OutputRequestReadQuery, *, project_id: uuid.UUID,
            output_request_id: uuid.UUID) -> OutputRequestView:
        if (type(query) is not OutputRequestReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or type(project_id) is not uuid.UUID or not project_id.int
                or type(output_request_id) is not uuid.UUID or not output_request_id.int):
            raise OutputRequestReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if (not isinstance(now, datetime) or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise OutputRequestReadError("SYSTEM_UNAVAILABLE")
                user_id = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(user_id) is not uuid.UUID or not user_id.int:
                    raise OutputRequestReadError("AUTH_ACCESS_DENIED")
                project = self._projects.get_authorized(
                    transaction, user_id, project_id,
                )
                if project is None:
                    raise OutputRequestReadError("RESOURCE_NOT_FOUND")
                view = self._repository.get(
                    transaction, project_id=project_id,
                    output_request_id=output_request_id,
                )
                if type(view) is not OutputRequestView:
                    raise OutputRequestReadError("RESOURCE_NOT_FOUND")
                if view.project_id != project_id or view.output_request_id != output_request_id:
                    raise OutputRequestReadError("SYSTEM_UNAVAILABLE")
                return view
        except OutputRequestReadError:
            raise
        except RuntimeLicenseError:
            raise OutputRequestReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutputRequestReadError("SYSTEM_UNAVAILABLE") from None
