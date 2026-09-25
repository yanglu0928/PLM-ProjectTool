"""Upload Commit: physical proof, then one short database publication transaction."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue, ParseJobRequest
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


_OPERATION = "V1_DOCUMENT_UPLOAD_COMMIT"


class UploadCommitError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CommitUpload:
    upload_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    expected_document_version: int | None
    max_bytes: int


@dataclass(frozen=True, slots=True)
class ReadyUpload:
    file_object_id: uuid.UUID
    staging_locator: str
    final_locator: str
    sha256: bytes
    size_bytes: int
    detected_mime: str
    file_lock_version: int
    intent_lock_version: int
    target_document_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class CommittedUploadVersion:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_no: int


@dataclass(frozen=True, slots=True)
class CommittedUpload:
    upload_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_no: int
    parse_job_id: uuid.UUID


class UploadCommitAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               upload_id: uuid.UUID, operation: str) -> None: ...


class UploadCommitRepositoryPort(Protocol):
    def preflight(self, transaction: object, *, command: CommitUpload) -> ReadyUpload: ...
    def commit(self, transaction: object, *, command: CommitUpload,
               expected: ReadyUpload) -> CommittedUploadVersion: ...
    def replay(self, transaction: object, *, command: CommitUpload) -> CommittedUploadVersion: ...


class UploadCommitReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class UploadCommitLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CommitUploadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: UploadCommitAccessPort,
                 repository: UploadCommitRepositoryPort, receipts: UploadCommitReceiptPort,
                 jobs: ParseJobQueue, audit: AuditService,
                 storage: LocalFileStorage, license_guard: UploadCommitLicensePort) -> None:
        if any(item is None for item in (unit_of_work, access, repository,
                                         receipts, jobs, audit, storage, license_guard)):
            raise ValueError("Upload commit dependencies are required")
        self._uow, self._access, self._repository = unit_of_work, access, repository
        self._receipts, self._jobs, self._audit = receipts, jobs, audit
        self._storage, self._license_guard = storage, license_guard

    def commit(self, command: CommitUpload, *, idempotency_key: str) -> CommittedUpload:
        self._validate(command)
        validate_idempotency_key(idempotency_key)
        receipt_scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=_OPERATION, key=idempotency_key,
        )
        fingerprint = canonical_payload_fingerprint({
            "upload_id": str(command.upload_id), "scope": command.scope,
            "project_id": str(command.project_id),
            "expected_document_version": command.expected_document_version,
        })
        self._licensed(command)
        with self._uow() as tx:
            self._authorize(tx, command)
            receipt = self._receipts.reserve(
                tx, scope=receipt_scope, request_fingerprint=fingerprint,
            )
            if receipt is not None:
                result = self._replay(tx, command, receipt)
                tx.commit()
                return result
            ready = self._repository.preflight(tx, command=command)
            # This provisional receipt rolls back. Hashing and physical promotion
            # must not keep a database transaction open.
        self._publish_physical(ready, max_bytes=command.max_bytes)
        self._licensed(command)
        with self._uow() as tx:
            self._authorize(tx, command)
            receipt = self._receipts.reserve(
                tx, scope=receipt_scope, request_fingerprint=fingerprint,
            )
            if receipt is not None:
                result = self._replay(tx, command, receipt)
                tx.commit()
                return result
            version = self._repository.commit(tx, command=command, expected=ready)
            job_ref = self._enqueue(tx, command, version)
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_UPLOAD_COMMIT", outcome="SUCCESS",
                target_owner_module="document", target_object_type="DOC-02",
                target_object_id=version.document_id,
                target_version_id=version.document_version_id,
                before_state=None, after_state="AVAILABLE",
            ))
            self._receipts.complete(
                tx, scope=receipt_scope,
                result=IdempotencyResult(_OPERATION, command.upload_id, 201),
            )
            tx.commit()
            return CommittedUpload(command.upload_id, version.document_id,
                                   version.document_version_id, version.version_no,
                                   job_ref.job_id)

    def _replay(self, tx: object, command: CommitUpload,
                receipt: IdempotencyResult) -> CommittedUpload:
        if receipt.ref_type != _OPERATION or receipt.ref_id != command.upload_id or receipt.status_code != 201:
            raise UploadCommitError("FILE_UNAVAILABLE")
        version = self._repository.replay(tx, command=command)
        job_ref = self._enqueue(tx, command, version)
        return CommittedUpload(command.upload_id, version.document_id,
                               version.document_version_id, version.version_no,
                               job_ref.job_id)

    def _enqueue(self, tx: object, command: CommitUpload,
                 version: CommittedUploadVersion):
        return self._jobs.enqueue_parse(tx, request=ParseJobRequest(
            upload_id=command.upload_id, document_id=version.document_id,
            document_version_id=version.document_version_id,
            version_no=version.version_no, scope=command.scope,
            project_id=command.project_id, actor_id=command.actor_id,
            trace_id=command.trace_id,
        ))

    def _publish_physical(self, ready: ReadyUpload, *, max_bytes: int) -> None:
        claims = dict(expected_sha256=ready.sha256, expected_size=ready.size_bytes,
                      max_bytes=max_bytes)
        try:
            self._storage.publish_verified(
                ready.staging_locator, ready.final_locator, **claims,
            )
            return
        except LocalStorageError:
            pass
        try:
            inspection = self._storage.inspect_recovery(
                ready.staging_locator, ready.final_locator, **claims,
            )
            if inspection.shape == "FINAL_VERIFIED":
                self._storage.recover_verified_final(
                    ready.staging_locator, ready.final_locator, **claims,
                )
            elif inspection.shape == "LINKED_PAIR":
                self._storage.recover_linked_pair(
                    ready.staging_locator, ready.final_locator, **claims,
                )
            else:
                raise LocalStorageError()
        except LocalStorageError:
            raise UploadCommitError("FILE_INTEGRITY_MISMATCH") from None

    def _licensed(self, command: CommitUpload) -> None:
        self._license_guard.require_valid(trace_id=command.trace_id)

    def _authorize(self, tx: object, command: CommitUpload) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, upload_id=command.upload_id,
            operation=_OPERATION,
        )

    @staticmethod
    def _validate(command: CommitUpload) -> None:
        if (type(command) is not CommitUpload
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.upload_id, command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or (command.scope == "GLOBAL" and command.project_id is not None)
                or (command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0))
                or (command.expected_document_version is not None and (
                    type(command.expected_document_version) is not int
                    or command.expected_document_version < 0))
                or type(command.max_bytes) is not int or command.max_bytes < 0):
            raise UploadCommitError("VALIDATION_FAILED")
