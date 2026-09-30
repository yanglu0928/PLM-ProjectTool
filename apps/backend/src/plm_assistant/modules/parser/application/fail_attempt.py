"""Fenced Parser failure: Document, Audit, and Jobs in one short UOW."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_failure import (
    FailedParseAttempt, ParseFailureRequest,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding

from .prepare_input import ParserInputCommand

FATAL_CODES = frozenset({
    "PARSER_INPUT_INVALID", "PARSER_INPUT_CHANGED", "FILE_INTEGRITY_MISMATCH",
    "PARSER_FORMAT_UNSUPPORTED", "PARSER_OCR_ENGINE_REQUIRED",
    "PARSER_RESULT_INVALID", "PARSER_RESULT_LIMIT_EXCEEDED",
    "PARSER_OFFICE_LIMIT_EXCEEDED", "PARSER_TEXT_ENCODING_INVALID",
    "PARSER_CSV_INVALID", "PARSER_OFFICE_INVALID", "PARSER_PDF_ENCRYPTED",
    "PARSER_OCR_REQUIRED", "PARSER_PDF_INVALID", "PARSER_OCR_ENGINE_INVALID",
    "PARSER_IMAGE_INVALID", "PARSER_IMAGE_ORIENTATION_UNSUPPORTED",
    "PARSER_OCR_NO_TEXT", "PARSER_OCR_RESULT_INVALID",
})
RETRY_CODES = frozenset({
    "PARSER_INPUT_UNAVAILABLE", "PARSER_OCR_FAILED",
    "PARSER_RUNTIME_UNAVAILABLE", "PARSER_STORAGE_UNAVAILABLE",
})


def classify_parser_failure(error: Exception, *, attempt_no: int
                            ) -> tuple[str, bool, int]:
    """Map only known safe codes; never persist arbitrary exception text."""
    if type(attempt_no) is not int or not 1 <= attempt_no <= 3:
        raise ParserFailureError("VALIDATION_FAILED")
    candidate = getattr(error, "code", None)
    if type(candidate) is str and candidate in (FATAL_CODES | RETRY_CODES):
        code = candidate
    else:
        code = "PARSER_RUNTIME_UNAVAILABLE"
    retryable = code in RETRY_CODES
    return code, retryable, ({1: 5, 2: 15, 3: 0}[attempt_no] if retryable else 0)


class ParserFailureError(RuntimeError):
    def __init__(self, code: str = "PARSER_FAILURE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParserFailureOutcome:
    job_state: str
    parse_record_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if (self.job_state not in {"RETRY_WAIT", "FAILED"}
                or (self.parse_record_id is not None and
                    (type(self.parse_record_id) is not uuid.UUID or self.parse_record_id.int == 0))):
            raise ParserFailureError()


class LeasePort(Protocol):
    def check_current(self, tx: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def retry_or_fail(self, tx: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str, error_code: str,
                      retryable: bool, delay_seconds: int) -> str: ...


class QueuePort(Protocol):
    def peek_parse_for_job(self, tx: object, *, job_id: uuid.UUID
                           ) -> ParseJobBinding | None: ...


class DocumentPort(Protocol):
    def fail_started(self, tx: object, *, request: ParseFailureRequest
                     ) -> FailedParseAttempt: ...


class AuditPort(Protocol):
    def append(self, tx: object, event: AuditEventDraft) -> uuid.UUID: ...


class FailParserAttempt:
    def __init__(self, *, unit_of_work: Callable[[], object], leases: LeasePort,
                 queue: QueuePort, documents: DocumentPort, audit: AuditPort,
                 system_actor_id: uuid.UUID) -> None:
        if (any(value is None for value in (unit_of_work, leases, queue, documents, audit))
                or type(system_actor_id) is not uuid.UUID or system_actor_id.int == 0):
            raise ValueError("Parser failure dependencies required")
        self._uow, self._leases, self._queue = unit_of_work, leases, queue
        self._documents, self._audit = documents, audit
        self._system_actor_id = system_actor_id

    def fail(self, *, command: ParserInputCommand, started: StartedParseAttempt | None,
             error_code: str, retryable: bool, delay_seconds: int
             ) -> ParserFailureOutcome:
        if (type(command) is not ParserInputCommand
                or (started is not None and type(started) is not StartedParseAttempt)
                or error_code not in (FATAL_CODES | RETRY_CODES)
                or type(retryable) is not bool
                or type(delay_seconds) is not int
                or not 0 <= delay_seconds <= 300
                or (not retryable and delay_seconds != 0)):
            raise ParserFailureError("VALIDATION_FAILED")
        try:
            command.__post_init__()
            if started is not None:
                started.__post_init__()
            with self._uow() as tx:
                claim = self._leases.check_current(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token, worker_ref=command.worker_ref)
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if (type(claim) is not ClaimedJob or type(binding) is not ParseJobBinding
                        or claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.job_type != "DOCUMENT_PARSE"
                        or claim.attempt_no not in (1, 2, 3)):
                    raise ParserFailureError()
                binding.__post_init__()
                request = binding.request
                if ((claim.scope, claim.project_id, claim.trace_id, claim.payload_refs)
                        != (request.scope, request.project_id, str(request.trace_id),
                            {"document_id": str(request.document_id),
                             "document_version_id": str(request.document_version_id)})):
                    raise ParserFailureError()
                record_id = None
                if started is not None:
                    if ((started.job_id, started.document_version_id,
                         started.attempt_no)
                            != (claim.job_id, request.document_version_id,
                                claim.attempt_no)):
                        raise ParserFailureError("PARSER_ATTEMPT_CONFLICT")
                    failed = self._documents.fail_started(tx,
                        request=ParseFailureRequest(started, request.scope,
                            request.project_id, error_code, retryable))
                    if (type(failed) is not FailedParseAttempt
                            or failed.parse_record_id != started.parse_record_id):
                        raise ParserFailureError()
                    failed.__post_init__()
                    record_id = failed.parse_record_id
                event = self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id,
                    event_scope="PROJECT" if request.scope == "PROJECT" else "DEPLOYMENT",
                    target_project_id=request.project_id,
                    actor_type="SYSTEM", actor_id=self._system_actor_id,
                    original_actor_id=request.actor_id, actor_hint_digest=None,
                    action="DOCUMENT_PARSE_FAILED", outcome="FAILED",
                    target_owner_module="document",
                    target_object_type="DOC-04" if record_id is not None else "DOC-02",
                    target_object_id=record_id or request.document_version_id,
                    target_version_id=request.document_version_id,
                    before_state="RUNNING" if record_id is not None else None,
                    after_state="FAILED" if record_id is not None else None,
                    reason_code=error_code,
                ))
                if type(event) is not uuid.UUID or event.int == 0:
                    raise ParserFailureError()
                state = self._leases.retry_or_fail(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token, worker_ref=command.worker_ref,
                    error_code=error_code, retryable=retryable,
                    delay_seconds=delay_seconds)
                if state not in {"RETRY_WAIT", "FAILED"}:
                    raise ParserFailureError()
                tx.commit()
                return ParserFailureOutcome(state, record_id)
        except ParserFailureError:
            raise
        except JobLeaseError as exc:
            if exc.code == "STALE_LEASE":
                raise ParserFailureError("STALE_LEASE") from None
            raise ParserFailureError() from None
        except Exception:
            raise ParserFailureError() from None
