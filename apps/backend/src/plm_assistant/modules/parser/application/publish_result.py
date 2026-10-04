"""Fenced Parser success: private bytes, Document result, Audit, then Job finish."""

from __future__ import annotations

import hmac
import uuid
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_job_source import DocumentParseInputSource
from plm_assistant.modules.document.application.parse_publish import (
    ParseSuccessRequest, PublishedParseResult, StoredParseResult,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding

from .prepare_input import ParserInputCommand, VerifiedParserInput
from .system_actor_binding import ParserSystemActorBinding
from .profile_selection import ParserInputVersion, choose_parser_profile
from .structured_result import ParsedResult


class ParserPublishError(RuntimeError):
    def __init__(self, code: str = "PARSER_PUBLISH_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class LeasePort(Protocol):
    def check_current(self, tx: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def finish(self, tx: object, *, job_id: uuid.UUID,
               fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class QueuePort(Protocol):
    def peek_parse_for_job(self, tx: object, *, job_id: uuid.UUID
                           ) -> ParseJobBinding | None: ...


class DocumentPort(Protocol):
    def read_input(self, tx: object, *, request: object) -> DocumentParseInputSource: ...


class ResultStoragePort(Protocol):
    def read_verified(self, *, scope: str, project_id: uuid.UUID | None,
                      result_ref_id: uuid.UUID, expected_locator: str,
                      expected_sha256: bytes, expected_size: int) -> bytes: ...


class PublishPort(Protocol):
    def publish_success(self, tx: object, *, request: ParseSuccessRequest
                        ) -> PublishedParseResult: ...


class AuditPort(Protocol):
    def append(self, tx: object, event: AuditEventDraft) -> uuid.UUID: ...


class PublishParserResult:
    def __init__(self, *, unit_of_work: Callable[[], object], leases: LeasePort,
                 queue: QueuePort, documents: DocumentPort,
                 storage: ResultStoragePort, results: PublishPort,
                 audit: AuditPort, system_actor_id: uuid.UUID | None = None,
                 system_actor: object | None = None) -> None:
        if (any(value is None for value in (unit_of_work, leases, queue,
                                            documents, storage, results, audit))):
            raise ValueError("Parser publication dependencies required")
        self._uow, self._leases, self._queue = unit_of_work, leases, queue
        self._documents, self._storage, self._results = documents, storage, results
        self._audit = audit
        self._system_actor = ParserSystemActorBinding(
            system_actor_id=system_actor_id, system_actor=system_actor)

    def publish(self, *, command: ParserInputCommand, prepared: VerifiedParserInput,
                started: StartedParseAttempt, parsed: ParsedResult,
                stored: StoredParseResult) -> PublishedParseResult:
        if (type(command) is not ParserInputCommand
                or type(prepared) is not VerifiedParserInput
                or type(started) is not StartedParseAttempt
                or type(parsed) is not ParsedResult
                or type(stored) is not StoredParseResult):
            raise ParserPublishError("VALIDATION_FAILED")
        try:
            command.__post_init__()
            started.__post_init__()
            parsed.__post_init__()
            stored.__post_init__()
            identity = self._system_actor.capture()
            plan = prepared.plan
            if (plan != choose_parser_profile(plan.source)
                    or (prepared.job_id, prepared.fencing_token, prepared.attempt_no)
                       != (command.job_id, command.fencing_token, started.attempt_no)
                    or prepared.attempt_no not in (1, 2, 3)
                    or (started.job_id, started.document_version_id,
                        started.parser_profile, started.parser_version)
                       != (command.job_id, plan.source.document_version_id,
                           plan.parser_profile, plan.parser_version)
                    or (parsed.document_version_id, parsed.source_sha256,
                        parsed.parser_profile, parsed.parser_version, parsed.schema_version)
                       != (plan.source.document_version_id, plan.source.content_sha256,
                           plan.parser_profile, plan.parser_version, "1")):
                raise ParserPublishError("PARSER_RESULT_MISMATCH")
            canonical = parsed.canonical_bytes()
            if (len(canonical) != stored.size_bytes
                    or not hmac.compare_digest(parsed.result_sha256(), stored.sha256)):
                raise ParserPublishError("PARSER_RESULT_MISMATCH")
            # No DB lock is held during bounded physical I/O.
            scope, project_id = self._source_scope(stored.storage_locator)
            physical = self._storage.read_verified(
                scope=scope, project_id=project_id,
                result_ref_id=stored.result_ref_id,
                expected_locator=stored.storage_locator,
                expected_sha256=stored.sha256, expected_size=stored.size_bytes)
            if type(physical) is not bytes or not hmac.compare_digest(physical, canonical):
                raise ParserPublishError("PARSER_RESULT_MISMATCH")
            with self._uow() as tx:
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if type(binding) is not ParseJobBinding or binding.refs.job_id != command.job_id:
                    raise ParserPublishError()
                binding.__post_init__()
                request = binding.request
                source = self._documents.read_input(tx, request=request)
                if (type(source) is not DocumentParseInputSource
                        or source.committed.request != request):
                    raise ParserPublishError()
                source.__post_init__()
                claim = self._leases.check_current(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token, worker_ref=command.worker_ref)
                if (type(claim) is not ClaimedJob or claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.attempt_no != prepared.attempt_no
                        or claim.job_type != "DOCUMENT_PARSE"):
                    raise ParserPublishError()
                if ((claim.scope, claim.project_id, claim.trace_id, claim.payload_refs)
                        != (request.scope, request.project_id, str(request.trace_id),
                            {"document_id": str(request.document_id),
                             "document_version_id": str(request.document_version_id)})
                        or (scope, project_id) != (request.scope, request.project_id)):
                    raise ParserPublishError("PARSER_RESULT_MISMATCH")
                expected = ParserInputVersion(request.document_version_id,
                    source.content_sha256, source.size_bytes, source.detected_mime)
                if plan != choose_parser_profile(expected):
                    raise ParserPublishError("PARSER_INPUT_CHANGED")
                published = self._results.publish_success(tx, request=ParseSuccessRequest(
                    started.parse_record_id, command.job_id,
                    request.document_version_id, request.scope, request.project_id,
                    plan.parser_profile, plan.parser_version,
                    prepared.attempt_no, stored))
                if (type(published) is not PublishedParseResult
                        or (published.parse_record_id, published.result_ref_id)
                        != (started.parse_record_id, stored.result_ref_id)):
                    raise ParserPublishError()
                published.__post_init__()
                event = self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id,
                    event_scope="PROJECT" if request.scope == "PROJECT" else "DEPLOYMENT",
                    target_project_id=request.project_id,
                    actor_type="SYSTEM", actor_id=identity,
                    original_actor_id=request.actor_id, actor_hint_digest=None,
                    action="DOCUMENT_PARSE_SUCCEEDED", outcome="SUCCESS",
                    target_owner_module="document", target_object_type="DOC-04",
                    target_object_id=started.parse_record_id,
                    target_version_id=request.document_version_id,
                    before_state="RUNNING", after_state="SUCCEEDED",
                ))
                if type(event) is not uuid.UUID or event.int == 0:
                    raise ParserPublishError()
                finished = self._leases.finish(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token, worker_ref=command.worker_ref)
                if type(finished) is not ClaimedJob or finished != claim:
                    raise ParserPublishError()
                self._system_actor.assert_same(identity)
                tx.commit()
                return published
        except ParserPublishError:
            raise
        except JobLeaseError as exc:
            if exc.code == "STALE_LEASE":
                raise ParserPublishError("STALE_LEASE") from None
            raise ParserPublishError() from None
        except Exception:
            raise ParserPublishError() from None

    @staticmethod
    def _source_scope(locator: str) -> tuple[str, uuid.UUID | None]:
        parts = locator.split("/") if type(locator) is str else []
        if len(parts) == 4 and parts[:2] == ["results", "global"]:
            return "GLOBAL", None
        if len(parts) == 5 and parts[:2] == ["results", "projects"]:
            try:
                project_id = uuid.UUID(hex=parts[2])
            except ValueError:
                raise ParserPublishError("PARSER_RESULT_MISMATCH") from None
            if project_id.int != 0 and parts[2] == project_id.hex:
                return "PROJECT", project_id
        raise ParserPublishError("PARSER_RESULT_MISMATCH")
