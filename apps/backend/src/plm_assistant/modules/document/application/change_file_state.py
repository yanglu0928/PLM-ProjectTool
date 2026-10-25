"""Internal fail/restrict FileObject commands; no upload or HTTP entry point."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_TARGETS = {"FAILED": "V1_DOCUMENT_FILE_FAIL",
            "RESTRICTED": "V1_DOCUMENT_FILE_RESTRICT"}


class FileStateCommandError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ChangeFileState:
    file_object_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    expected_version: int
    target_state: str
    reason_code: str


class FileStateAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               operation: str) -> None: ...


class FileStateRepositoryPort(Protocol):
    def change(self, transaction: object, *, command: ChangeFileState) -> uuid.UUID: ...


class FileStateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class FileStateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: FileStateAccessPort, repository: FileStateRepositoryPort,
                 receipts: FileStateReceiptPort, audit: AuditService) -> None:
        if any(value is None for value in (unit_of_work, access, repository, receipts, audit)):
            raise ValueError("FileObject state dependencies are required")
        self._unit_of_work = unit_of_work
        self._access = access
        self._repository = repository
        self._receipts = receipts
        self._audit = audit

    def change(self, command: ChangeFileState, *, idempotency_key: str) -> uuid.UUID:
        """Return an immutable state-event ID; replay never repeats write/Audit."""
        self._validate(command)
        validate_idempotency_key(idempotency_key)
        operation = _TARGETS[command.target_state]
        fingerprint = canonical_payload_fingerprint({
            "file_object_id": str(command.file_object_id),
            "scope": command.scope, "project_id": str(command.project_id),
            "expected_version": command.expected_version,
            "target_state": command.target_state, "reason_code": command.reason_code,
        })
        with self._unit_of_work() as tx:
            self._access.require_in_transaction(
                tx, actor_id=command.actor_id, scope=command.scope,
                project_id=command.project_id, operation=operation,
            )
            scope = IdempotencyScope.from_key(
                actor_id=command.actor_id, project_id=command.project_id,
                operation=operation, key=idempotency_key,
            )
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if replay.ref_type != operation:
                    raise FileStateCommandError("FILE_UNAVAILABLE")
                tx.commit()
                return replay.ref_id
            event_id = self._repository.change(tx, command=command)
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_FILE_" + command.target_state,
                outcome="SUCCESS", target_owner_module="document",
                target_object_type="DOC-03", target_object_id=command.file_object_id,
                reason_code=command.reason_code,
                before_state="STAGED" if command.target_state == "FAILED" else "AVAILABLE",
                after_state=command.target_state,
            ))
            self._receipts.complete(
                tx, scope=scope,
                result=IdempotencyResult(operation, event_id, 200),
            )
            tx.commit()
            return event_id

    @staticmethod
    def _validate(command: ChangeFileState) -> None:
        if (type(command) is not ChangeFileState
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.file_object_id, command.actor_id, command.trace_id,
                ))
                or type(command.scope) is not str
                or command.scope not in ("GLOBAL", "PROJECT")
                or (command.scope == "GLOBAL" and command.project_id is not None)
                or (command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0))
                or type(command.expected_version) is not int or command.expected_version < 0
                or type(command.target_state) is not str
                or command.target_state not in _TARGETS
                or type(command.reason_code) is not str
                or _REASON.fullmatch(command.reason_code) is None):
            raise FileStateCommandError("VALIDATION_FAILED")
