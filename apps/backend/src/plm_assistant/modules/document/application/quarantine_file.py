"""Explicit, quiescence-gated internal isolation of failed STAGED content."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.application.publish_file import (
    FilePublishAccessPort, FilePublishError, FilePublishReceiptPort,
    FilePublishService, PublishFile, StagedFile,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


_OPERATION = "V1_DOCUMENT_FILE_QUARANTINE"
_REASONS = {
    "NONE": "FILE_RECOVERY_MISSING",
    "STAGE_ONLY": "FILE_RECOVERY_UNPROMOTED",
    "FINAL_INVALID": "FILE_RECOVERY_INVALID",
    "BOTH_UNRELATED": "FILE_RECOVERY_CONFLICT",
}


class FileRecoveryQuiescencePort(Protocol):
    def require_quiesced_in_transaction(self, transaction: object, *,
                                        scope: str,
                                        project_id: uuid.UUID | None) -> None: ...


class FileQuarantineRepositoryPort(Protocol):
    def staged(self, transaction: object, *, command: PublishFile) -> StagedFile: ...
    def staged_locked(self, transaction: object, *, command: PublishFile) -> StagedFile: ...
    def quarantine(self, transaction: object, *, command: PublishFile,
                   expected: StagedFile, reason_code: str) -> uuid.UUID: ...


class FileQuarantineService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: FilePublishAccessPort,
                 quiescence: FileRecoveryQuiescencePort,
                 repository: FileQuarantineRepositoryPort,
                 receipts: FilePublishReceiptPort,
                 audit: AuditService, storage: LocalFileStorage) -> None:
        if any(value is None for value in (
            unit_of_work, access, quiescence, repository, receipts, audit, storage,
        )):
            raise ValueError("FileObject quarantine dependencies are required")
        self._unit_of_work = unit_of_work
        self._access = access
        self._quiescence = quiescence
        self._repository = repository
        self._receipts = receipts
        self._audit = audit
        self._storage = storage

    def quarantine(self, command: PublishFile, *, idempotency_key: str) -> uuid.UUID:
        FilePublishService._validate(command)
        validate_idempotency_key(idempotency_key)
        scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=_OPERATION, key=idempotency_key,
        )
        fingerprint = canonical_payload_fingerprint({
            "file_object_id": str(command.file_object_id), "scope": command.scope,
            "project_id": str(command.project_id),
            "expected_version": command.expected_version,
            "max_bytes": command.max_bytes,
        })
        with self._unit_of_work() as tx:
            self._require_safe(tx, command)
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != _OPERATION:
                    raise FilePublishError("FILE_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            staged = self._repository.staged(tx, command=command)
        inspection = self._inspect(staged, command)
        reason_code = _REASONS.get(inspection)
        if reason_code is None:
            raise FilePublishError("FILE_RECOVERY_REVIEW_REQUIRED")
        with self._unit_of_work() as tx:
            self._require_safe(tx, command)
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != _OPERATION:
                    raise FilePublishError("FILE_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            # Rare maintenance operation: hold a DB row lock while repeating
            # the bounded inspection, after rechecking immutable metadata.
            if self._repository.staged_locked(tx, command=command) != staged:
                raise FilePublishError("CONFLICT_VERSION")
            if self._inspect(staged, command) != inspection:
                raise FilePublishError("CONFLICT_STATE")
            event_id = self._repository.quarantine(
                tx, command=command, expected=staged, reason_code=reason_code,
            )
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_FILE_QUARANTINE", outcome="SUCCESS",
                target_owner_module="document", target_object_type="DOC-03",
                target_object_id=command.file_object_id, reason_code=reason_code,
                before_state="STAGED", after_state="FAILED",
            ))
            self._receipts.complete(
                tx, scope=scope, result=IdempotencyResult(_OPERATION, event_id, 200),
            )
            tx.commit()
            return event_id

    def _require_safe(self, tx: object, command: PublishFile) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, operation=_OPERATION,
        )
        self._quiescence.require_quiesced_in_transaction(
            tx, scope=command.scope, project_id=command.project_id,
        )

    def _inspect(self, staged: StagedFile, command: PublishFile) -> str:
        return self._storage.inspect_recovery(
            staged.staging_locator, staged.final_locator,
            expected_sha256=staged.sha256, expected_size=staged.size_bytes,
            max_bytes=command.max_bytes,
        ).shape
