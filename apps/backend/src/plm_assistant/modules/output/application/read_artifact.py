"""Authorized, fixed OutputArtifact reference reads; never returns storage locators."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class OutputArtifactReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutputArtifactReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OutputArtifactReference:
    output_artifact_id: uuid.UUID
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    artifact_kind: str
    media_type: str
    content_sha256: str
    size_bytes: int


class OutputArtifactReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class OutputArtifactProjectReadPort(Protocol):
    def get_authorized(self, transaction: object, user_id: uuid.UUID,
                       project_id: uuid.UUID) -> object | None: ...


class OutputArtifactReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class OutputArtifactReadRepositoryPort(Protocol):
    def get_available(self, transaction: object, *, project_id: uuid.UUID,
                      output_request_id: uuid.UUID) -> OutputArtifactReference | None: ...


class OutputArtifactReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: OutputArtifactReadAccessPort,
                 projects: OutputArtifactProjectReadPort,
                 license_guard: OutputArtifactReadLicensePort,
                 repository: OutputArtifactReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in
               (unit_of_work, access, projects, license_guard, repository)):
            raise ValueError("OutputArtifact read dependencies are required")
        self._uow, self._access, self._projects = unit_of_work, access, projects
        self._guard, self._repository = license_guard, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_available(self, query: OutputArtifactReadQuery, *, project_id: uuid.UUID,
                      output_request_id: uuid.UUID) -> OutputArtifactReference:
        if (type(query) is not OutputArtifactReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or type(project_id) is not uuid.UUID or not project_id.int
                or type(output_request_id) is not uuid.UUID or not output_request_id.int):
            raise OutputArtifactReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                    raise OutputArtifactReadError("SYSTEM_UNAVAILABLE")
                user_id = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(user_id) is not uuid.UUID or not user_id.int:
                    raise OutputArtifactReadError("AUTH_ACCESS_DENIED")
                if self._projects.get_authorized(transaction, user_id, project_id) is None:
                    raise OutputArtifactReadError("RESOURCE_NOT_FOUND")
                result = self._repository.get_available(
                    transaction, project_id=project_id,
                    output_request_id=output_request_id,
                )
                if (type(result) is not OutputArtifactReference
                        or result.project_id != project_id
                        or result.output_request_id != output_request_id
                        or not result.output_artifact_id.int
                        or not result.document_id.int
                        or not result.document_version_id.int):
                    raise OutputArtifactReadError("RESOURCE_NOT_FOUND")
                return result
        except OutputArtifactReadError:
            raise
        except RuntimeLicenseError:
            raise OutputArtifactReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutputArtifactReadError("SYSTEM_UNAVAILABLE") from None
