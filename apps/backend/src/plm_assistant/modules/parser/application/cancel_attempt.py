"""Cooperative Parser cancellation in one fenced Document/Audit/Jobs UOW."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_cancel import (
    CancelledParseAttempt, ParseCancelRequest,
)
from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, ParserLeasePulse,
)
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding

from .prepare_input import ParserInputCommand
from .system_actor_binding import ParserSystemActorBinding


class ParserCancellationError(RuntimeError):
    def __init__(self, code: str = "PARSER_CANCEL_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParserCancellationOutcome:
    job_id: uuid.UUID
    parse_record_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if (type(self.job_id) is not uuid.UUID or self.job_id.int == 0
                or (self.parse_record_id is not None and
                    (type(self.parse_record_id) is not uuid.UUID or self.parse_record_id.int == 0))):
            raise ParserCancellationError()


class LeasePort(Protocol):
    def pulse_parse(self, tx: object, *, job_id: uuid.UUID,
                    fencing_token: int, worker_ref: str,
                    lease_seconds: int) -> ParserLeasePulse: ...
    def acknowledge_parse_cancel(self, tx: object, *, job_id: uuid.UUID,
                                 fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class QueuePort(Protocol):
    def peek_parse_for_job(self, tx: object, *, job_id: uuid.UUID
                           ) -> ParseJobBinding | None: ...


class DocumentPort(Protocol):
    def cancel_current(self, tx: object, *, request: ParseCancelRequest
                       ) -> CancelledParseAttempt | None: ...


class AuditPort(Protocol):
    def append(self, tx: object, event: AuditEventDraft) -> uuid.UUID: ...


class AcknowledgeParserCancel:
    def __init__(self, *, unit_of_work: Callable[[], object], leases: LeasePort,
                 queue: QueuePort, documents: DocumentPort, audit: AuditPort,
                 system_actor_id: uuid.UUID | None = None,
                 system_actor: object | None = None) -> None:
        if any(value is None for value in (unit_of_work, leases, queue, documents, audit)):
            raise ValueError("Parser cancellation dependencies required")
        self._uow, self._leases, self._queue = unit_of_work, leases, queue
        self._documents, self._audit = documents, audit
        self._system_actor = ParserSystemActorBinding(
            system_actor_id=system_actor_id, system_actor=system_actor)

    def acknowledge(self, *, command: ParserInputCommand,
                    started: StartedParseAttempt | None) -> ParserCancellationOutcome:
        if (type(command) is not ParserInputCommand
                or (started is not None and type(started) is not StartedParseAttempt)):
            raise ParserCancellationError("VALIDATION_FAILED")
        try:
            command.__post_init__()
            identity = self._system_actor.capture()
            with self._uow() as tx:
                pulse = self._leases.pulse_parse(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token,
                    worker_ref=command.worker_ref, lease_seconds=1)
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if (type(pulse) is not ParserLeasePulse
                        or pulse.state != "CANCEL_REQUESTED"
                        or type(binding) is not ParseJobBinding):
                    raise ParserCancellationError("STALE_LEASE")
                pulse.__post_init__()
                binding.__post_init__()
                claim = pulse.claim
                request = binding.request
                if (claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.job_type != "DOCUMENT_PARSE"
                        or claim.attempt_no not in (1, 2, 3)
                        or (claim.scope, claim.project_id, claim.trace_id, claim.payload_refs)
                        != (request.scope, request.project_id, str(request.trace_id),
                            {"document_id": str(request.document_id),
                             "document_version_id": str(request.document_version_id)})):
                    raise ParserCancellationError()
                cancelled = self._documents.cancel_current(tx,
                    request=ParseCancelRequest(command.job_id,
                        request.document_version_id, request.scope,
                        request.project_id, claim.attempt_no, started))
                if cancelled is not None:
                    if type(cancelled) is not CancelledParseAttempt:
                        raise ParserCancellationError()
                    cancelled.__post_init__()
                record_id = cancelled.parse_record_id if cancelled is not None else None
                event = self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id,
                    event_scope="PROJECT" if request.scope == "PROJECT" else "DEPLOYMENT",
                    target_project_id=request.project_id,
                    actor_type="SYSTEM", actor_id=identity,
                    original_actor_id=request.actor_id, actor_hint_digest=None,
                    action="DOCUMENT_PARSE_CANCELLED", outcome="SUCCESS",
                    target_owner_module="document",
                    target_object_type="DOC-04" if record_id is not None else "DOC-02",
                    target_object_id=record_id or request.document_version_id,
                    target_version_id=request.document_version_id,
                    before_state="RUNNING" if record_id is not None else None,
                    after_state="CANCELLED" if record_id is not None else None,
                    reason_code="JOB_CANCELLED",
                ))
                if type(event) is not uuid.UUID or event.int == 0:
                    raise ParserCancellationError()
                closed = self._leases.acknowledge_parse_cancel(tx,
                    job_id=command.job_id, fencing_token=command.fencing_token,
                    worker_ref=command.worker_ref)
                if type(closed) is not ClaimedJob or closed != claim:
                    raise ParserCancellationError()
                self._system_actor.assert_same(identity)
                tx.commit()
                return ParserCancellationOutcome(command.job_id, record_id)
        except ParserCancellationError:
            raise
        except JobLeaseError as exc:
            if exc.code == "STALE_LEASE":
                raise ParserCancellationError("STALE_LEASE") from None
            raise ParserCancellationError() from None
        except Exception:
            raise ParserCancellationError() from None
