"""Cross-module Port for committing a Parse Job and Outbox in caller's transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


class ParseEnqueueError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParseJobRequest:
    upload_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_no: int
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ParseJobRef:
    job_id: uuid.UUID
    event_id: uuid.UUID


class ParseJobQueuePort(Protocol):
    def enqueue_parse(self, transaction: object, *, request: ParseJobRequest) -> ParseJobRef: ...


class ParseJobQueue:
    """Validate the stable cross-owner request; never start or commit a transaction."""

    def __init__(self, repository: ParseJobQueuePort) -> None:
        if repository is None:
            raise ValueError("Parse job repository is required")
        self._repository = repository

    def enqueue_parse(self, transaction: object, *, request: ParseJobRequest) -> ParseJobRef:
        if (type(request) is not ParseJobRequest
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    request.upload_id, request.document_id,
                    request.document_version_id, request.actor_id, request.trace_id,
                ))
                or type(request.version_no) is not int or request.version_no < 1
                or request.scope not in ("GLOBAL", "PROJECT")
                or (request.scope == "GLOBAL" and request.project_id is not None)
                or (request.scope == "PROJECT" and (
                    type(request.project_id) is not uuid.UUID or request.project_id.int == 0))):
            raise ParseEnqueueError("VALIDATION_FAILED")
        return self._repository.enqueue_parse(transaction, request=request)
