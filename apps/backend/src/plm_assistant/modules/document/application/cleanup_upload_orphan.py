"""Explicit maintenance command for one expired, unregistered upload file."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage, LocalStorageError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
)


_OPERATION = "V1_DOCUMENT_ORPHAN_CLEANUP"
_SEVEN_DAYS = 604_800


class OrphanCleanupError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CleanupUploadOrphan:
    upload_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID


class OrphanCleanupAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               upload_id: uuid.UUID, operation: str) -> None: ...


class OrphanCleanupRepositoryPort(Protocol):
    def require_eligible(self, transaction: object, *, command: CleanupUploadOrphan,
                         ttl_seconds: int, modified_ns: int) -> int: ...


class OrphanCleanupReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CleanupUploadOrphanService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: OrphanCleanupAccessPort,
                 repository: OrphanCleanupRepositoryPort,
                 receipts: OrphanCleanupReceiptPort,
                 audit: AuditService, storage: LocalFileStorage,
                 ttl_seconds: int = _SEVEN_DAYS) -> None:
        if (any(value is None for value in (unit_of_work, access, repository, receipts, audit, storage))
                or type(ttl_seconds) is not int or ttl_seconds < _SEVEN_DAYS):
            raise ValueError("Invalid orphan cleanup dependencies or retention")
        self._uow, self._access, self._repository = unit_of_work, access, repository
        self._receipts = receipts
        self._audit, self._storage, self._ttl = audit, storage, ttl_seconds

    def cleanup_one(self, command: CleanupUploadOrphan) -> bool:
        self._validate(command)
        with self._uow() as tx:
            self._authorize(tx, command)
        try:
            locator, _ = self._storage.locators(
                scope=command.scope, project_id=command.project_id,
                file_object_id=command.upload_id,
            )
            snapshot = self._storage.inspect_staging_for_cleanup(locator)
        except LocalStorageError:
            raise OrphanCleanupError("FILE_CONTENT_UNAVAILABLE") from None
        if snapshot is None:
            return False
        scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=_OPERATION, key="orphan-" + command.upload_id.hex,
        )
        fingerprint = canonical_payload_fingerprint({
            "upload_id": str(command.upload_id), "scope": command.scope,
            "project_id": str(command.project_id), "ttl_seconds": self._ttl,
        })
        with self._uow() as tx:
            self._authorize(tx, command)
            cutoff_ns = self._repository.require_eligible(
                tx, command=command, ttl_seconds=self._ttl,
                modified_ns=snapshot.modified_ns,
            )
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is None:
                self._audit.append(tx, self._event(command, "DOCUMENT_ORPHAN_CLEANUP_REQUESTED"))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, command.upload_id, 202),
                )
            elif (replay.ref_type != _OPERATION or replay.ref_id != command.upload_id):
                raise OrphanCleanupError("CONFLICT_STATE")
            tx.commit()
        try:
            self._storage.discard_stale_staging(
                locator, snapshot=snapshot, cutoff_ns=cutoff_ns,
            )
        except LocalStorageError:
            raise OrphanCleanupError("FILE_CONTENT_UNAVAILABLE") from None
        with self._uow() as tx:
            self._audit.append(tx, self._event(command, "DOCUMENT_ORPHAN_CLEANUP_COMPLETED"))
            tx.commit()
        return True

    def _authorize(self, tx: object, command: CleanupUploadOrphan) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, upload_id=command.upload_id,
            operation=_OPERATION,
        )

    @staticmethod
    def _event(command: CleanupUploadOrphan, action: str) -> AuditEventDraft:
        return AuditEventDraft(
            trace_id=command.trace_id,
            event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
            target_project_id=command.project_id,
            actor_type="USER", actor_id=command.actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action=action, outcome="SUCCESS",
            target_owner_module="document", target_object_type="DOC-03",
            target_object_id=command.upload_id,
            before_state="ORPHAN", after_state="CLEANUP_PENDING" if action.endswith("REQUESTED") else "REMOVED",
        )

    @staticmethod
    def _validate(command: CleanupUploadOrphan) -> None:
        if (type(command) is not CleanupUploadOrphan
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.upload_id, command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or command.scope == "GLOBAL" and command.project_id is not None
                or command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0)):
            raise OrphanCleanupError("VALIDATION_FAILED")
