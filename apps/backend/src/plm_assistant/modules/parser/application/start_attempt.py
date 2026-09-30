"""Start a first ParseRecord only for a currently fenced, verified Job input."""

from __future__ import annotations

import uuid
from typing import Callable, Protocol

from plm_assistant.modules.document.application.parse_attempt import (
    DocumentParseAttemptRequest, ParseAttemptError, StartedParseAttempt,
)
from plm_assistant.modules.document.application.parse_job_source import DocumentParseInputSource
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding

from .prepare_input import ParserInputCommand, VerifiedParserInput
from .profile_selection import ParserInputVersion, choose_parser_profile


class LeasePort(Protocol):
    def check_current(self, tx: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class QueuePort(Protocol):
    def peek_parse_for_job(self, tx: object, *, job_id: uuid.UUID
                           ) -> ParseJobBinding | None: ...


class DocumentPort(Protocol):
    def read_input(self, tx: object, *, request: object) -> DocumentParseInputSource: ...


class AttemptPort(Protocol):
    def start_first(self, tx: object, *, job_id: uuid.UUID,
                    request: DocumentParseAttemptRequest,
                    scope: str, project_id: uuid.UUID | None) -> StartedParseAttempt: ...


class StartFirstParseAttempt:
    def __init__(self, *, unit_of_work: Callable[[], object], leases: LeasePort,
                 queue: QueuePort, documents: DocumentPort, attempts: AttemptPort) -> None:
        if any(value is None for value in (unit_of_work, leases, queue, documents, attempts)):
            raise ValueError("current Parser attempt dependencies required")
        self._uow = unit_of_work
        self._leases = leases
        self._queue = queue
        self._documents = documents
        self._attempts = attempts

    def start(self, command: ParserInputCommand,
              prepared: VerifiedParserInput) -> StartedParseAttempt:
        if (type(command) is not ParserInputCommand
                or type(prepared) is not VerifiedParserInput
                or (prepared.job_id, prepared.fencing_token, prepared.attempt_no)
                   != (command.job_id, command.fencing_token, 1)):
            raise ParseAttemptError("VALIDATION_FAILED")
        try:
            command.__post_init__()
            plan = prepared.plan
            if plan != choose_parser_profile(plan.source) or prepared.stream.closed:
                raise ParseAttemptError("PARSER_INPUT_CHANGED")
            with self._uow() as tx:
                claim = self._leases.check_current(
                    tx, job_id=command.job_id, fencing_token=command.fencing_token,
                    worker_ref=command.worker_ref)
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if (type(claim) is not ClaimedJob or type(binding) is not ParseJobBinding
                        or claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.attempt_no != 1 or claim.job_type != "DOCUMENT_PARSE"):
                    raise ParseAttemptError()
                binding.__post_init__()
                request = binding.request
                if ((claim.scope, claim.project_id, claim.trace_id, claim.payload_refs)
                        != (request.scope, request.project_id, str(request.trace_id),
                            {"document_id": str(request.document_id),
                             "document_version_id": str(request.document_version_id)})):
                    raise ParseAttemptError()
                source = self._documents.read_input(tx, request=request)
                if (type(source) is not DocumentParseInputSource
                        or source.committed.request != request):
                    raise ParseAttemptError()
                source.__post_init__()
                expected = ParserInputVersion(request.document_version_id,
                    source.content_sha256, source.size_bytes, source.detected_mime)
                if plan != choose_parser_profile(expected):
                    raise ParseAttemptError("PARSER_INPUT_CHANGED")
                started = self._attempts.start_first(
                    tx, job_id=command.job_id,
                    request=DocumentParseAttemptRequest(
                        expected.document_version_id, expected.content_sha256,
                        expected.size_bytes, expected.detected_mime,
                        plan.parser_profile, plan.parser_version),
                    scope=request.scope, project_id=request.project_id)
                if (type(started) is not StartedParseAttempt
                        or (started.job_id, started.document_version_id,
                            started.parser_profile, started.parser_version)
                        != (command.job_id, expected.document_version_id,
                            plan.parser_profile, plan.parser_version)):
                    raise ParseAttemptError()
                started.__post_init__()
                tx.commit()
                return started
        except ParseAttemptError:
            raise
        except JobLeaseError as exc:
            if exc.code == "STALE_LEASE":
                raise ParseAttemptError("STALE_LEASE") from None
            raise ParseAttemptError() from None
        except Exception:
            raise ParseAttemptError() from None
