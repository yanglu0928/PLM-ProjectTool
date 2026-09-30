"""Reconcile predecessor ParseRecords and start a newly fenced Job generation."""

from __future__ import annotations

import uuid
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.parse_attempt import (
    DocumentParseAttemptRequest, ParseAttemptError, ReconciledParseAttempt,
    StartedParseAttempt,
)
from plm_assistant.modules.document.application.parse_job_source import DocumentParseInputSource
from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, ClosedJobAttempt, JobLeaseError,
)
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding

from .prepare_input import ParserInputCommand, VerifiedParserInput
from .profile_selection import ParserInputVersion, choose_parser_profile


class LeasePort(Protocol):
    def check_current(self, tx: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def closed_attempts_for_current(self, tx: object, *, job_id: uuid.UUID,
                                    fencing_token: int, worker_ref: str
                                    ) -> tuple[ClosedJobAttempt, ...]: ...


class QueuePort(Protocol):
    def peek_parse_for_job(self, tx: object, *, job_id: uuid.UUID
                           ) -> ParseJobBinding | None: ...


class DocumentPort(Protocol):
    def read_input(self, tx: object, *, request: object) -> DocumentParseInputSource: ...


class AttemptPort(Protocol):
    def start_retry(self, tx: object, *, job_id: uuid.UUID,
                    request: DocumentParseAttemptRequest, scope: str,
                    project_id: uuid.UUID | None, attempt_no: int,
                    closed: tuple[ClosedJobAttempt, ...]
                    ) -> tuple[StartedParseAttempt, tuple[ReconciledParseAttempt, ...]]: ...


class AuditPort(Protocol):
    def append(self, tx: object, event: AuditEventDraft) -> uuid.UUID: ...


class StartRetryParseAttempt:
    def __init__(self, *, unit_of_work: Callable[[], object], leases: LeasePort,
                 queue: QueuePort, documents: DocumentPort, attempts: AttemptPort,
                 audit: AuditPort, system_actor_id: uuid.UUID) -> None:
        if (any(value is None for value in (unit_of_work, leases, queue,
                                            documents, attempts, audit))
                or type(system_actor_id) is not uuid.UUID or system_actor_id.int == 0):
            raise ValueError("Parser retry dependencies required")
        self._uow, self._leases, self._queue = unit_of_work, leases, queue
        self._documents, self._attempts = documents, attempts
        self._audit, self._system_actor_id = audit, system_actor_id

    def start(self, command: ParserInputCommand,
              prepared: VerifiedParserInput) -> StartedParseAttempt:
        if (type(command) is not ParserInputCommand
                or type(prepared) is not VerifiedParserInput
                or prepared.job_id != command.job_id
                or prepared.fencing_token != command.fencing_token
                or prepared.attempt_no not in (2, 3)):
            raise ParseAttemptError("VALIDATION_FAILED")
        try:
            command.__post_init__()
            plan = prepared.plan
            if plan != choose_parser_profile(plan.source) or prepared.stream.closed:
                raise ParseAttemptError("PARSER_INPUT_CHANGED")
            with self._uow() as tx:
                claim = self._leases.check_current(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token, worker_ref=command.worker_ref)
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if (type(claim) is not ClaimedJob or type(binding) is not ParseJobBinding
                        or claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.attempt_no != prepared.attempt_no
                        or claim.job_type != "DOCUMENT_PARSE"):
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
                closed = self._leases.closed_attempts_for_current(tx,
                    job_id=command.job_id, fencing_token=command.fencing_token,
                    worker_ref=command.worker_ref)
                if (type(closed) is not tuple or len(closed) != claim.attempt_no - 1
                        or any(type(item) is not ClosedJobAttempt for item in closed)):
                    raise ParseAttemptError()
                started, changed = self._attempts.start_retry(tx, job_id=command.job_id,
                    request=DocumentParseAttemptRequest(
                        expected.document_version_id, expected.content_sha256,
                        expected.size_bytes, expected.detected_mime,
                        plan.parser_profile, plan.parser_version),
                    scope=request.scope, project_id=request.project_id,
                    attempt_no=claim.attempt_no, closed=closed)
                if (type(started) is not StartedParseAttempt or type(changed) is not tuple
                        or (started.job_id, started.document_version_id,
                            started.parser_profile, started.parser_version,
                            started.attempt_no)
                        != (command.job_id, expected.document_version_id,
                            plan.parser_profile, plan.parser_version, claim.attempt_no)):
                    raise ParseAttemptError()
                started.__post_init__()
                for prior in changed:
                    if type(prior) is not ReconciledParseAttempt:
                        raise ParseAttemptError()
                    prior.__post_init__()
                    event_id = self._audit.append(tx, AuditEventDraft(
                        trace_id=request.trace_id,
                        event_scope="PROJECT" if request.scope == "PROJECT" else "DEPLOYMENT",
                        target_project_id=request.project_id,
                        actor_type="SYSTEM", actor_id=self._system_actor_id,
                        original_actor_id=request.actor_id, actor_hint_digest=None,
                        action="DOCUMENT_PARSE_ATTEMPT_RECONCILED", outcome="SUCCESS",
                        target_owner_module="document", target_object_type="DOC-04",
                        target_object_id=prior.parse_record_id,
                        target_version_id=request.document_version_id,
                        before_state=prior.before_state, after_state=prior.after_state,
                    ))
                    if type(event_id) is not uuid.UUID or event_id.int == 0:
                        raise ParseAttemptError()
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
