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


def _validate_read_request(request):
    if (type(request) is not ParseJobRequest
        or any(type(v) is not uuid.UUID or not v.int for v in (request.upload_id,request.document_id,request.document_version_id,request.actor_id,request.trace_id))
        or type(request.version_no) is not int or not 1<=request.version_no<=2147483647
        or type(request.scope) is not str or request.scope not in ('GLOBAL','PROJECT')
        or request.scope=='GLOBAL' and request.project_id is not None
        or request.scope=='PROJECT' and (type(request.project_id) is not uuid.UUID or not request.project_id.int)):
        raise ParseEnqueueError('VALIDATION_FAILED')


@dataclass(frozen=True,slots=True)
class ParseJobBinding:
    """Jobs-owned coordinates, never Document source authority or HTTP payload."""
    request: ParseJobRequest
    refs: ParseJobRef
    def __post_init__(self):
        try:_validate_read_request(self.request)
        except ParseEnqueueError:raise ParseEnqueueError('JOB_STORE_UNAVAILABLE') from None
        if type(self.refs) is not ParseJobRef or any(type(v) is not uuid.UUID or not v.int for v in (self.refs.job_id,self.refs.event_id)):
            raise ParseEnqueueError('JOB_STORE_UNAVAILABLE')


class ParseJobQueuePort(Protocol):
    def enqueue_parse(self, transaction: object, *, request: ParseJobRequest) -> ParseJobRef: ...
    def peek_parse_for_job(self,transaction:object,*,job_id:uuid.UUID)->ParseJobBinding|None: ...
    def find_parse(self,transaction:object,*,request:ParseJobRequest)->ParseJobRef|None: ...


class ParseJobQueue:
    """Validate the stable cross-owner request; never start or commit a transaction."""

    def __init__(self, repository: ParseJobQueuePort) -> None:
        if repository is None:
            raise ValueError("Parse job repository is required")
        self._repository = repository

    def peek_parse_for_job(self,transaction,*,job_id):
        if type(job_id) is not uuid.UUID or not job_id.int:raise ParseEnqueueError('VALIDATION_FAILED')
        try:
            value=self._repository.peek_parse_for_job(transaction,job_id=job_id)
            if value is None:return None
            if type(value) is not ParseJobBinding or value.refs.job_id!=job_id:raise ParseEnqueueError('JOB_STORE_UNAVAILABLE')
            value.__post_init__();return value
        except ParseEnqueueError:raise
        except Exception:raise ParseEnqueueError('JOB_STORE_UNAVAILABLE') from None

    def find_parse(self,transaction,*,request):
        _validate_read_request(request)
        try:
            value=self._repository.find_parse(transaction,request=request)
            if value is None:return None
            if type(value) is not ParseJobRef or any(type(v) is not uuid.UUID or not v.int for v in (value.job_id,value.event_id)):
                raise ParseEnqueueError('JOB_STORE_UNAVAILABLE')
            return value
        except ParseEnqueueError:raise
        except Exception:raise ParseEnqueueError('JOB_STORE_UNAVAILABLE') from None

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
