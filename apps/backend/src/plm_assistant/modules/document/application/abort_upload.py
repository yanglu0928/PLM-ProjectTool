"""Abort an upload atomically; physical cleanup is a separate, guarded job."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


_OPERATION = "V1_DOCUMENT_UPLOAD_ABORT"


class UploadAbortError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AbortUpload:
    upload_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AbortedUpload:
    upload_id: uuid.UUID
    cleanup_pending: bool


class AbortAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               upload_id: uuid.UUID, operation: str) -> None: ...


class AbortRepositoryPort(Protocol):
    def abort(self, transaction: object, *, command: AbortUpload) -> AbortedUpload: ...
    def replay(self, transaction: object, *, command: AbortUpload) -> AbortedUpload: ...


class AbortReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AbortLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AbortUploadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AbortAccessPort,
                 repository: AbortRepositoryPort, receipts: AbortReceiptPort,
                 audit: AuditService, license_guard: AbortLicensePort) -> None:
        if any(item is None for item in (unit_of_work, access, repository,
                                         receipts, audit, license_guard)):
            raise ValueError("Upload abort dependencies are required")
        self._uow, self._access, self._repository = unit_of_work, access, repository
        self._receipts, self._audit, self._license_guard = receipts, audit, license_guard

    def abort(self, command: AbortUpload, *, idempotency_key: str) -> AbortedUpload:
        self._validate(command)
        validate_idempotency_key(idempotency_key)
        self._license_guard.require_valid(trace_id=command.trace_id)
        scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=_OPERATION, key=idempotency_key,
        )
        fingerprint = canonical_payload_fingerprint({
            "upload_id": str(command.upload_id), "scope": command.scope,
            "project_id": str(command.project_id),
        })
        with self._uow() as tx:
            self._access.require_in_transaction(
                tx, actor_id=command.actor_id, scope=command.scope,
                project_id=command.project_id, upload_id=command.upload_id,
                operation=_OPERATION,
            )
            receipt = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if receipt is not None:
                if (receipt.ref_type != _OPERATION or receipt.ref_id != command.upload_id
                        or receipt.status_code != 200):
                    raise UploadAbortError("FILE_UNAVAILABLE")
                result = self._repository.replay(tx, command=command)
                tx.commit()
                return result
            result = self._repository.abort(tx, command=command)
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_UPLOAD_ABORT", outcome="SUCCESS",
                target_owner_module="document", target_object_type="DOC-03",
                target_object_id=command.upload_id,
                before_state=None, after_state="ABORTED",
            ))
            self._receipts.complete(
                tx, scope=scope,
                result=IdempotencyResult(_OPERATION, command.upload_id, 200),
            )
            tx.commit()
            return result

    @staticmethod
    def _validate(command: AbortUpload) -> None:
        if (type(command) is not AbortUpload
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.upload_id, command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or (command.scope == "GLOBAL" and command.project_id is not None)
                or (command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0))):
            raise UploadAbortError("VALIDATION_FAILED")
