"""Fenced, source-bound and fully verified private Parser input snapshot.

This prepares bytes for a future Worker; it does not execute parsing or publish a
ParseRecord. The Worker must renew its lease while parsing and fence publication.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import BinaryIO, Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.document.application.parse_job_source import (
    DocumentParseInputSource, DocumentParseSourceError,
)
from plm_assistant.modules.document.application.prepare_download import DownloadStorageError
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseEnqueueError, ParseJobBinding,
)
from .profile_selection import (
    ParserInputVersion, ParserProfileError, ParserProfilePlan, choose_parser_profile,
)


class ParserInputError(RuntimeError):
    def __init__(self, code: str = "PARSER_INPUT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParserInputCommand:
    job_id: uuid.UUID
    fencing_token: int
    worker_ref: str

    def __post_init__(self) -> None:
        try:
            validate_checkpoint(job_id=self.job_id, fencing_token=self.fencing_token,
                                worker_ref=self.worker_ref)
        except JobLeaseError:
            raise ParserInputError("VALIDATION_FAILED") from None


@dataclass(slots=True)
class VerifiedParserInput:
    """Caller-owned verified byte snapshot; no physical locator or user session."""
    plan: ParserProfilePlan
    job_id: uuid.UUID
    fencing_token: int
    attempt_no: int
    stream: BinaryIO = field(repr=False)

    def close(self) -> None:
        self.stream.close()

    def __enter__(self) -> "VerifiedParserInput":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ParserLeasePort(Protocol):
    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> ClaimedJob: ...


class ParserQueuePort(Protocol):
    def peek_parse_for_job(self, transaction: object, *, job_id: uuid.UUID
                           ) -> ParseJobBinding | None: ...


class ParserDocumentPort(Protocol):
    def read_input(self, transaction: object, *, request: object
                   ) -> DocumentParseInputSource: ...


class ParserStoragePort(Protocol):
    def open_verified_snapshot(self, locator: str, *, expected_sha256: bytes,
                               expected_size: int, max_bytes: int) -> BinaryIO: ...


class ParserAuditPort(Protocol):
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID: ...


class PrepareParserInput:
    def __init__(self, *, unit_of_work: Callable[[], object], leases: ParserLeasePort,
                 queue: ParserQueuePort, documents: ParserDocumentPort,
                 storage: ParserStoragePort, audit: ParserAuditPort,
                 system_actor_id: uuid.UUID) -> None:
        if (any(value is None for value in (unit_of_work, leases, queue, documents,
                                            storage, audit))
                or type(system_actor_id) is not uuid.UUID or system_actor_id.int == 0):
            raise ValueError("Parser input dependencies are required")
        self._uow, self._leases, self._queue = unit_of_work, leases, queue
        self._documents, self._storage, self._audit = documents, storage, audit
        self._system_actor_id = system_actor_id

    def prepare(self, command: ParserInputCommand) -> VerifiedParserInput:
        if type(command) is not ParserInputCommand:
            raise ParserInputError("VALIDATION_FAILED")
        command.__post_init__()
        source, plan, attempt_no = self._bound_source(command)
        try:
            snapshot = self._storage.open_verified_snapshot(
                source.storage_locator, expected_sha256=source.content_sha256,
                expected_size=source.size_bytes, max_bytes=100_000_000,
            )
        except DownloadStorageError:
            self._record_integrity_failure(source)
            raise ParserInputError("FILE_INTEGRITY_MISMATCH") from None
        except Exception:
            raise ParserInputError() from None
        try:
            current, current_plan, current_attempt = self._bound_source(command)
            if (current != source or current_plan != plan
                    or current_attempt != attempt_no):
                raise ParserInputError("PARSER_INPUT_CHANGED")
            if not callable(getattr(snapshot, "read", None)) or not callable(getattr(snapshot, "close", None)):
                raise ParserInputError()
            return VerifiedParserInput(plan, command.job_id, command.fencing_token,
                                       attempt_no, snapshot)
        except BaseException:
            try:
                close = getattr(snapshot, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
            raise

    def _bound_source(self, command: ParserInputCommand
                      ) -> tuple[DocumentParseInputSource, ParserProfilePlan, int]:
        try:
            with self._uow() as tx:
                claim = self._leases.check_current(tx, job_id=command.job_id,
                    fencing_token=command.fencing_token, worker_ref=command.worker_ref)
                binding = self._queue.peek_parse_for_job(tx, job_id=command.job_id)
                if (type(claim) is not ClaimedJob or type(binding) is not ParseJobBinding
                        or binding.refs.job_id != command.job_id
                        or claim.job_id != command.job_id
                        or claim.fencing_token != command.fencing_token
                        or claim.job_type != "DOCUMENT_PARSE"
                        or type(claim.attempt_no) is not int or not 1 <= claim.attempt_no <= 3):
                    raise ParserInputError()
                binding.__post_init__()
                request = binding.request
                if (claim.scope, claim.project_id, claim.trace_id, claim.payload_refs) != (
                    request.scope, request.project_id, str(request.trace_id),
                    {"document_id": str(request.document_id),
                     "document_version_id": str(request.document_version_id)},
                ):
                    raise ParserInputError()
                source = self._documents.read_input(tx, request=request)
                if (type(source) is not DocumentParseInputSource
                        or source.committed.request != request):
                    raise ParserInputError()
                source.__post_init__()
                plan = choose_parser_profile(ParserInputVersion(
                    request.document_version_id, source.content_sha256,
                    source.size_bytes, source.detected_mime,
                ))
                return source, plan, claim.attempt_no
        except ParserInputError:
            raise
        except JobLeaseError as exc:
            if exc.code == "STALE_LEASE":
                raise ParserInputError("STALE_LEASE") from None
            raise ParserInputError() from None
        except ParserProfileError as exc:
            raise ParserInputError(exc.code) from None
        except (ParseEnqueueError, DocumentParseSourceError):
            raise ParserInputError() from None
        except Exception:
            raise ParserInputError() from None

    def _record_integrity_failure(self, source: DocumentParseInputSource) -> None:
        request = source.committed.request
        try:
            with self._uow() as tx:
                self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id,
                    event_scope="PROJECT" if request.scope == "PROJECT" else "DEPLOYMENT",
                    target_project_id=request.project_id,
                    actor_type="SYSTEM", actor_id=self._system_actor_id,
                    original_actor_id=request.actor_id, actor_hint_digest=None,
                    action="DOCUMENT_PARSE_INTEGRITY_FAILED", outcome="FAILED",
                    target_owner_module="document", target_object_type="DOC-03",
                    target_object_id=source.committed.file_object_id,
                    target_version_id=request.document_version_id,
                    reason_code="FILE_INTEGRITY_MISMATCH",
                ))
                tx.commit()
        except Exception:
            raise ParserInputError() from None
