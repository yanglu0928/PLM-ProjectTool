"""Current-authority minimum Context projection for AI consumption."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


class RAGContextReadError(RuntimeError):
    def __init__(self, code: str = "RAG_CONTEXT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGContextReadRequest:
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    retrieval_run_id: uuid.UUID
    context_bundle_id: uuid.UUID
    context_bundle_fingerprint: bytes = field(repr=False)
    record_count: int
    content_size_bytes: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                    self.project_id, self.requested_by, self.trace_id,
                    self.retrieval_run_id, self.context_bundle_id,
                ))
                or type(self.context_bundle_fingerprint) is not bytes
                or len(self.context_bundle_fingerprint) != 32
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 100
                or type(self.content_size_bytes) is not int
                or not 1 <= self.content_size_bytes <= 100_000_000):
            raise RAGContextReadError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class RAGContextProjection:
    retrieval_run_id: uuid.UUID
    context_bundle_id: uuid.UUID
    context_bundle_fingerprint: bytes = field(repr=False)
    record_count: int
    content_utf8: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.retrieval_run_id) is not uuid.UUID
                or not self.retrieval_run_id.int
                or type(self.context_bundle_id) is not uuid.UUID
                or not self.context_bundle_id.int
                or type(self.context_bundle_fingerprint) is not bytes
                or len(self.context_bundle_fingerprint) != 32
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 100
                or type(self.content_utf8) is not bytes
                or not 1 <= len(self.content_utf8) <= 100_000_000):
            raise RAGContextReadError()
        try:
            decoded = self.content_utf8.decode("utf-8")
        except UnicodeDecodeError:
            raise RAGContextReadError() from None
        if not decoded.strip():
            raise RAGContextReadError()


class RAGContextRepositoryPort(Protocol):
    def read_exact(self, transaction: object, *, request: RAGContextReadRequest
                   ) -> RAGContextProjection | None: ...


class RAGContextReadService:
    """Recheck current Project/License facts before returning bounded text."""

    def __init__(self, *, authorization: ProjectAuthorizationService,
                 license_guard: object, repository: RAGContextRepositoryPort) -> None:
        if any(value is None for value in (
                authorization, license_guard, repository)):
            raise ValueError("RAG Context read dependencies required")
        self._authorization = authorization
        self._guard = license_guard
        self._repository = repository

    def read_exact(self, transaction: object, *, request: RAGContextReadRequest
                   ) -> RAGContextProjection:
        if transaction is None or type(request) is not RAGContextReadRequest:
            raise RAGContextReadError("VALIDATION_FAILED")
        request.__post_init__()
        try:
            self._authorization.require_in_transaction(
                transaction, user_id=request.requested_by,
                project_id=request.project_id, operation="AI_TASK_EXECUTE",
            )
            self._guard.require_valid(trace_id=request.trace_id)
            result = self._repository.read_exact(transaction, request=request)
            self._guard.require_valid(trace_id=request.trace_id)
            if (type(result) is not RAGContextProjection
                    or result.retrieval_run_id != request.retrieval_run_id
                    or result.context_bundle_id != request.context_bundle_id
                    or result.context_bundle_fingerprint
                       != request.context_bundle_fingerprint
                    or result.record_count != request.record_count
                    or len(result.content_utf8) != request.content_size_bytes):
                raise RAGContextReadError()
            result.__post_init__()
            return result
        except RAGContextReadError:
            raise
        except ProjectAuthorizationError:
            raise RAGContextReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise RAGContextReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RAGContextReadError() from None
