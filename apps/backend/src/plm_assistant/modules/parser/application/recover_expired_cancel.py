"""Database-fenced recovery when a cancelled Parser worker misses its lease."""

from __future__ import annotations

import uuid

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.parse_cancel import ParseCancelRequest
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding

from .cancel_attempt import ParserCancellationError, ParserCancellationOutcome
from .prepare_input import ParserInputCommand


class RecoverExpiredParserCancel:
    """No process-kill assertion: stale publishers are fenced at their checkpoints."""

    def __init__(self, *, unit_of_work, leases, queue, sources, cancellations,
                 documents, audit, system_actor):
        if any(value is None for value in (unit_of_work, leases, queue, sources,
                                            cancellations, documents, audit, system_actor)):
            raise ValueError("Parser recovery dependencies required")
        self._uow, self._leases, self._queue, self._sources = (
            unit_of_work, leases, queue, sources)
        self._cancellations, self._documents = cancellations, documents
        self._audit, self._system_actor = audit, system_actor

    def _identity(self):
        try:
            identity = self._system_actor.assert_current()
            if type(identity) is not uuid.UUID or identity.int == 0:
                raise ValueError()
            return identity
        except Exception:
            raise ParserCancellationError("SYSTEM_ACTOR_UNAVAILABLE") from None

    def recover(self, *, command: ParserInputCommand) -> ParserCancellationOutcome:
        if type(command) is not ParserInputCommand:
            raise ParserCancellationError("VALIDATION_FAILED")
        command.__post_init__()
        identity = self._identity()
        try:
            with self._uow() as tx:
                claim, requester, requested_at = self._leases.expired_parse_cancel_facts(
                    tx, job_id=command.job_id, fencing_token=command.fencing_token,
                    worker_ref=command.worker_ref)
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if type(claim) is not ClaimedJob or type(binding) is not ParseJobBinding:
                    raise ParserCancellationError()
                request = binding.request
                if (claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.job_type != "DOCUMENT_PARSE" or claim.scope != "PROJECT"
                        or (claim.scope, claim.project_id, claim.trace_id, claim.payload_refs)
                        != (request.scope, request.project_id, str(request.trace_id),
                            {"document_id": str(request.document_id),
                             "document_version_id": str(request.document_version_id)})):
                    raise ParserCancellationError()
                self._sources.read(tx, request=request)
                first = self._cancellations.first_request(tx, job_id=command.job_id,
                    project_id=request.project_id, requested_by=requester,
                    requested_at=requested_at)
                state, changed = self._cancellations.receipt(tx, job_id=command.job_id,
                    project_id=request.project_id, actor_id=requester, event_id=first)
                if state != "CANCEL_REQUESTED" or changed is not True:
                    raise ParserCancellationError()
                cancelled = self._documents.cancel_current(tx, request=ParseCancelRequest(
                    command.job_id, request.document_version_id, request.scope,
                    request.project_id, claim.attempt_no, None))
                record_id = cancelled.parse_record_id if cancelled is not None else None
                event_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id, event_scope="PROJECT",
                    target_project_id=request.project_id, actor_type="SYSTEM",
                    actor_id=identity, original_actor_id=requester,
                    actor_hint_digest=None, action="DOCUMENT_PARSE_CANCEL_RECOVERED",
                    outcome="SUCCESS", target_owner_module="jobs",
                    target_object_type="JOB-01", target_object_id=command.job_id,
                    target_version_id=request.document_version_id,
                    before_state="CANCEL_REQUESTED", after_state="CANCELLED",
                    reason_code="LEASE_EXPIRED"))
                if type(event_id) is not uuid.UUID or event_id.int == 0:
                    raise ParserCancellationError()
                if self._identity() != identity:
                    raise ParserCancellationError("SYSTEM_ACTOR_UNAVAILABLE")
                closed = self._leases.recover_expired_parse_cancel(tx,
                    job_id=command.job_id, fencing_token=command.fencing_token,
                    worker_ref=command.worker_ref)
                if type(closed) is not ClaimedJob or closed != claim:
                    raise ParserCancellationError()
                tx.commit()
                return ParserCancellationOutcome(command.job_id, record_id)
        except ParserCancellationError:
            raise
        except JobLeaseError as exc:
            raise ParserCancellationError(
                "STALE_LEASE" if exc.code == "STALE_LEASE" else "PARSER_CANCEL_UNAVAILABLE") from None
        except Exception:
            raise ParserCancellationError() from None

    def verify_committed(self, *, command: ParserInputCommand) -> ParserCancellationOutcome:
        """Read-only post-commit proof for an uncertain commit acknowledgement."""
        if type(command) is not ParserInputCommand:
            raise ParserCancellationError("VALIDATION_FAILED")
        command.__post_init__()
        try:
            with self._uow() as tx:
                claim, requester, requested_at, completed_at = (
                    self._leases.recovered_parse_cancel_facts(tx, job_id=command.job_id,
                        fencing_token=command.fencing_token, worker_ref=command.worker_ref))
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if type(binding) is not ParseJobBinding:
                    raise ParserCancellationError()
                request = binding.request
                if (claim.job_id != command.job_id or claim.fencing_token != command.fencing_token
                        or (claim.scope, claim.project_id, claim.trace_id, claim.payload_refs)
                        != (request.scope, request.project_id, str(request.trace_id),
                            {"document_id": str(request.document_id),
                             "document_version_id": str(request.document_version_id)})):
                    raise ParserCancellationError()
                self._sources.read(tx, request=request)
                first = self._cancellations.first_request(tx, job_id=command.job_id,
                    project_id=request.project_id, requested_by=requester,
                    requested_at=requested_at)
                state, changed = self._cancellations.receipt(tx, job_id=command.job_id,
                    project_id=request.project_id, actor_id=requester, event_id=first)
                if state != "CANCEL_REQUESTED" or changed is not True:
                    raise ParserCancellationError()
                cancelled = self._documents.verified_cancelled_current(tx,
                    request=ParseCancelRequest(command.job_id,
                        request.document_version_id, request.scope, request.project_id,
                        claim.attempt_no, None))
                if cancelled is not None and cancelled.completed_at > completed_at:
                    raise ParserCancellationError()
                event_id = self._cancellations.verified_recovery(tx,
                    job_id=command.job_id, project_id=request.project_id,
                    document_version_id=request.document_version_id,
                    trace_id=request.trace_id, original_actor_id=requester,
                    requested_at=requested_at, completed_at=completed_at)
                if type(event_id) is not uuid.UUID or event_id.int == 0:
                    raise ParserCancellationError()
                return ParserCancellationOutcome(command.job_id,
                    cancelled.parse_record_id if cancelled is not None else None)
        except ParserCancellationError:
            raise
        except Exception:
            raise ParserCancellationError() from None
