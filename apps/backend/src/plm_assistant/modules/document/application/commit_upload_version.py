"""Internal commit of an uploaded immutable DocumentVersion."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


_OPERATION = "V1_DOCUMENT_VERSION_COMMIT_UPLOAD"


class DocumentVersionCommitError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CommitUploadVersion:
    document_id: uuid.UUID
    file_object_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    expected_document_version: int
    max_bytes: int


@dataclass(frozen=True, slots=True)
class PublishedFileSnapshot:
    locator: str
    sha256: bytes
    size_bytes: int
    detected_mime: str
    lock_version: int


class DocumentVersionCommitAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               document_id: uuid.UUID, operation: str) -> None: ...


class DocumentVersionCommitRepositoryPort(Protocol):
    def prepared(self, transaction: object, *, command: CommitUploadVersion) -> PublishedFileSnapshot: ...
    def commit(self, transaction: object, *, command: CommitUploadVersion,
               expected: PublishedFileSnapshot) -> uuid.UUID: ...


class DocumentVersionCommitReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CommitUploadVersionService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: DocumentVersionCommitAccessPort,
                 repository: DocumentVersionCommitRepositoryPort,
                 receipts: DocumentVersionCommitReceiptPort,
                 audit: AuditService, storage: LocalFileStorage) -> None:
        if any(value is None for value in (
            unit_of_work, access, repository, receipts, audit, storage,
        )):
            raise ValueError("DocumentVersion commit dependencies are required")
        self._unit_of_work = unit_of_work
        self._access = access
        self._repository = repository
        self._receipts = receipts
        self._audit = audit
        self._storage = storage

    def commit(self, command: CommitUploadVersion, *, idempotency_key: str) -> uuid.UUID:
        self._validate(command)
        validate_idempotency_key(idempotency_key)
        scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=_OPERATION, key=idempotency_key,
        )
        fingerprint = canonical_payload_fingerprint({
            "document_id": str(command.document_id),
            "file_object_id": str(command.file_object_id),
            "scope": command.scope, "project_id": str(command.project_id),
            "expected_document_version": command.expected_document_version,
            "max_bytes": command.max_bytes,
        })
        with self._unit_of_work() as tx:
            self._authorize(tx, command)
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != _OPERATION:
                    raise DocumentVersionCommitError("DOCUMENT_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            snapshot = self._repository.prepared(tx, command=command)
        proof = self._storage.verify_content(
            snapshot.locator, expected_sha256=snapshot.sha256,
            expected_size=snapshot.size_bytes, max_bytes=command.max_bytes,
        )
        if (proof.locator != snapshot.locator or proof.sha256 != snapshot.sha256
                or proof.size_bytes != snapshot.size_bytes):
            raise DocumentVersionCommitError("DOCUMENT_UNAVAILABLE")
        with self._unit_of_work() as tx:
            self._authorize(tx, command)
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != _OPERATION:
                    raise DocumentVersionCommitError("DOCUMENT_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            version_id = self._repository.commit(tx, command=command, expected=snapshot)
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_VERSION_COMMIT_UPLOAD", outcome="SUCCESS",
                target_owner_module="document", target_object_type="DOC-01",
                target_object_id=command.document_id, target_version_id=version_id,
                reason_code=None, before_state=None, after_state="AVAILABLE",
            ))
            self._receipts.complete(
                tx, scope=scope, result=IdempotencyResult(_OPERATION, version_id, 201),
            )
            tx.commit()
            return version_id

    def _authorize(self, tx: object, command: CommitUploadVersion) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, document_id=command.document_id,
            operation=_OPERATION,
        )

    @staticmethod
    def _validate(command: CommitUploadVersion) -> None:
        if (type(command) is not CommitUploadVersion
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.document_id, command.file_object_id,
                    command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or (command.scope == "GLOBAL" and command.project_id is not None)
                or (command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0))
                or type(command.expected_document_version) is not int
                or command.expected_document_version < 0
                or type(command.max_bytes) is not int or command.max_bytes < 0):
            raise DocumentVersionCommitError("VALIDATION_FAILED")
