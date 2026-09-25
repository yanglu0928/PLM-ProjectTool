"""Internal, authorized FileObject publication; never exposed as HTTP directly."""

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


_OPERATION = "V1_DOCUMENT_FILE_PUBLISH"
_RECOVER_OPERATION = "V1_DOCUMENT_FILE_RECOVER"
_LINKED_RECOVER_OPERATION = "V1_DOCUMENT_FILE_LINKED_RECOVER"


class FilePublishError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PublishFile:
    file_object_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    expected_version: int
    max_bytes: int


@dataclass(frozen=True, slots=True)
class StagedFile:
    staging_locator: str
    final_locator: str
    sha256: bytes
    size_bytes: int


class FilePublishAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               operation: str) -> None: ...


class FilePublishRepositoryPort(Protocol):
    def staged(self, transaction: object, *, command: PublishFile) -> StagedFile: ...
    def publish(self, transaction: object, *, command: PublishFile,
                expected: StagedFile) -> uuid.UUID: ...


class FilePublishReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class FilePublishService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: FilePublishAccessPort,
                 repository: FilePublishRepositoryPort, receipts: FilePublishReceiptPort,
                 audit: AuditService, storage: LocalFileStorage) -> None:
        if any(value is None for value in (
            unit_of_work, access, repository, receipts, audit, storage,
        )):
            raise ValueError("FileObject publish dependencies are required")
        self._unit_of_work = unit_of_work
        self._access = access
        self._repository = repository
        self._receipts = receipts
        self._audit = audit
        self._storage = storage

    def publish(self, command: PublishFile, *, idempotency_key: str) -> uuid.UUID:
        return self._run(command, idempotency_key=idempotency_key, mode="publish")

    def recover_final_only(self, command: PublishFile, *, idempotency_key: str) -> uuid.UUID:
        """Complete a known final-only crash window after rechecking the bytes."""
        return self._run(command, idempotency_key=idempotency_key, mode="final_only")

    def recover_linked_pair(self, command: PublishFile, *, idempotency_key: str) -> uuid.UUID:
        """Finish the exact two-hard-link crash window after content proof."""
        return self._run(command, idempotency_key=idempotency_key, mode="linked_pair")

    def _run(self, command: PublishFile, *, idempotency_key: str,
             mode: str) -> uuid.UUID:
        self._validate(command)
        validate_idempotency_key(idempotency_key)
        operation = {
            "publish": _OPERATION,
            "final_only": _RECOVER_OPERATION,
            "linked_pair": _LINKED_RECOVER_OPERATION,
        }[mode]
        scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=operation, key=idempotency_key,
        )
        fingerprint = canonical_payload_fingerprint({
            "file_object_id": str(command.file_object_id), "scope": command.scope,
            "project_id": str(command.project_id),
            "expected_version": command.expected_version,
            "max_bytes": command.max_bytes,
        })
        # This short transaction authorizes and snapshots metadata; do not hold a
        # database lock while hashing potentially large files.
        with self._unit_of_work() as tx:
            self._authorize(tx, command, operation=operation)
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != operation:
                    raise FilePublishError("FILE_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            staged = self._repository.staged(tx, command=command)
            # Roll back the provisional receipt; it must be committed only with
            # the state event, Audit, and AVAILABLE update below.
        verify = {
            "publish": self._storage.publish_verified,
            "final_only": self._storage.recover_verified_final,
            "linked_pair": self._storage.recover_linked_pair,
        }[mode]
        proof = verify(
            staged.staging_locator, staged.final_locator,
            expected_sha256=staged.sha256, expected_size=staged.size_bytes,
            max_bytes=command.max_bytes,
        )
        if (proof.locator != staged.final_locator or proof.sha256 != staged.sha256
                or proof.size_bytes != staged.size_bytes):
            raise FilePublishError("FILE_UNAVAILABLE")
        with self._unit_of_work() as tx:
            self._authorize(tx, command, operation=operation)
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != operation:
                    raise FilePublishError("FILE_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            event_id = self._repository.publish(tx, command=command, expected=staged)
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_FILE_PUBLISH" if mode == "publish" else "DOCUMENT_FILE_RECOVER",
                outcome="SUCCESS",
                target_owner_module="document", target_object_type="DOC-03",
                target_object_id=command.file_object_id, reason_code=None,
                before_state="STAGED", after_state="AVAILABLE",
            ))
            self._receipts.complete(
                tx, scope=scope, result=IdempotencyResult(operation, event_id, 200),
            )
            tx.commit()
            return event_id

    def _authorize(self, tx: object, command: PublishFile, *, operation: str) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, operation=operation,
        )

    @staticmethod
    def _validate(command: PublishFile) -> None:
        if (type(command) is not PublishFile
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.file_object_id, command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or (command.scope == "GLOBAL" and command.project_id is not None)
                or (command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0))
                or type(command.expected_version) is not int or command.expected_version < 0
                or type(command.max_bytes) is not int or command.max_bytes < 0):
            raise FilePublishError("VALIDATION_FAILED")
