"""Internal fenced cleanup of one registered, aborted upload with durable Audit."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.application.inspect_registered_abort import (
    RegisteredAbortCandidate, RegisteredAbortInspectionError,
)
from plm_assistant.modules.document.application.upload_operation_gate import (
    UploadGateUnavailable, UploadOperationGatePort,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalStorageError


_OPERATION = "V1_DOCUMENT_REGISTERED_ABORT_CLEANUP"
_REQUESTED = "DOCUMENT_REGISTERED_ABORT_CLEANUP_REQUESTED"
_COMPLETED = "DOCUMENT_REGISTERED_ABORT_CLEANUP_COMPLETED"
_ABSENT = "DOCUMENT_REGISTERED_ABORT_CLEANUP_ABSENT"


class RegisteredAbortCleanupError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CleanupRegisteredAbort:
    upload_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID


class RegisteredAbortCleanupAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               upload_id: uuid.UUID, operation: str) -> None: ...


class RegisteredAbortCleanupRepositoryPort(Protocol):
    def candidate(self, transaction: object, upload_id: uuid.UUID, *,
                  lock: bool = False) -> RegisteredAbortCandidate | None: ...

    def requested(self, transaction: object, upload_id: uuid.UUID) -> bool: ...

    def completed(self, transaction: object, *, upload_id: uuid.UUID,
                  scope: str, project_id: uuid.UUID | None) -> bool: ...

    def mark_removed(self, transaction: object, *, expected: RegisteredAbortCandidate,
                     actor_id: uuid.UUID, trace_id: uuid.UUID,
                     reconciled_absent: bool) -> None: ...


class RegisteredAbortCleanupStoragePort(Protocol):
    def verified_registered_abort_shape(self, staging_locator: str,
                                        final_locator: str, *,
                                        expected_sha256: bytes,
                                        expected_size: int, max_bytes: int) -> str: ...

    def discard_one_registered_aborted(self, staging_locator: str, final_locator: str,
                                       *, expected_sha256: bytes, expected_size: int,
                                       max_bytes: int) -> str: ...


class CleanupRegisteredAbortService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: RegisteredAbortCleanupAccessPort,
                 repository: RegisteredAbortCleanupRepositoryPort,
                 audit: AuditService, storage: RegisteredAbortCleanupStoragePort,
                 operation_gate: UploadOperationGatePort) -> None:
        if any(item is None for item in (unit_of_work, access, repository, audit,
                                         storage, operation_gate)):
            raise ValueError("registered abort cleanup dependencies are required")
        self._uow, self._access, self._repo = unit_of_work, access, repository
        self._audit, self._storage, self._gate = audit, storage, operation_gate

    def cleanup_one(self, command: CleanupRegisteredAbort) -> bool:
        self._validate(command)
        try:
            with self._gate.hold(command.upload_id):
                return self._cleanup_held(command)
        except (UploadGateUnavailable, LocalStorageError, RegisteredAbortInspectionError):
            raise RegisteredAbortCleanupError("FILE_CONTENT_UNAVAILABLE") from None

    def _cleanup_held(self, command: CleanupRegisteredAbort) -> bool:
        with self._uow() as tx:
            self._authorize(tx, command)
            candidate = self._repo.candidate(tx, command.upload_id)
            if candidate is None:
                return self._replay_completed(tx, command)
            self._match(candidate, command)
            requested = self._repo.requested(tx, command.upload_id)
        shape = self._shape(candidate)
        if shape == "NONE" and not requested:
            raise RegisteredAbortCleanupError("FILE_CONTENT_UNAVAILABLE")
        with self._uow() as tx:
            self._authorize(tx, command)
            if self._repo.candidate(tx, command.upload_id, lock=True) != candidate:
                raise RegisteredAbortCleanupError("CONFLICT_STATE")
            if not self._repo.requested(tx, command.upload_id):
                if shape == "NONE":
                    raise RegisteredAbortCleanupError("FILE_CONTENT_UNAVAILABLE")
                self._audit.append(tx, self._event(command, _REQUESTED))
            tx.commit()
        removed_this_call = False
        for _ in range(3):
            with self._uow() as tx:
                self._authorize(tx, command)
                if self._repo.candidate(tx, command.upload_id) != candidate:
                    raise RegisteredAbortCleanupError("CONFLICT_STATE")
            if self._shape(candidate) == "NONE":
                break
            result = self._storage.discard_one_registered_aborted(
                candidate.staging_locator, candidate.final_locator,
                expected_sha256=candidate.sha256,
                expected_size=candidate.size_bytes, max_bytes=100_000_000,
            )
            if result == "NONE":
                break
            if result not in ("STAGE_REMOVED", "FINAL_REMOVED"):
                raise RegisteredAbortCleanupError("FILE_CONTENT_UNAVAILABLE")
            removed_this_call = True
        else:
            raise RegisteredAbortCleanupError("FILE_CONTENT_UNAVAILABLE")
        if self._shape(candidate) != "NONE":
            raise RegisteredAbortCleanupError("FILE_CONTENT_UNAVAILABLE")
        with self._uow() as tx:
            self._authorize(tx, command)
            if self._repo.candidate(tx, command.upload_id, lock=True) != candidate:
                raise RegisteredAbortCleanupError("CONFLICT_STATE")
            self._repo.mark_removed(
                tx, expected=candidate, actor_id=command.actor_id,
                trace_id=command.trace_id,
                reconciled_absent=not removed_this_call,
            )
            self._audit.append(tx, self._event(
                command, _ABSENT if not removed_this_call else _COMPLETED,
            ))
            tx.commit()
        return True

    def _shape(self, candidate: RegisteredAbortCandidate) -> str:
        return self._storage.verified_registered_abort_shape(
            candidate.staging_locator, candidate.final_locator,
            expected_sha256=candidate.sha256,
            expected_size=candidate.size_bytes, max_bytes=100_000_000,
        )

    def _replay_completed(self, tx: object, command: CleanupRegisteredAbort) -> bool:
        if self._repo.completed(tx, upload_id=command.upload_id,
                                scope=command.scope, project_id=command.project_id):
            return False
        raise RegisteredAbortCleanupError("CONFLICT_STATE")

    def _authorize(self, tx: object, command: CleanupRegisteredAbort) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, upload_id=command.upload_id,
            operation=_OPERATION,
        )

    @staticmethod
    def _match(candidate: RegisteredAbortCandidate, command: CleanupRegisteredAbort) -> None:
        if (candidate.scope != command.scope
                or candidate.project_id != command.project_id):
            raise RegisteredAbortCleanupError("CONFLICT_STATE")

    @staticmethod
    def _event(command: CleanupRegisteredAbort, action: str) -> AuditEventDraft:
        return AuditEventDraft(
            trace_id=command.trace_id,
            event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
            target_project_id=command.project_id,
            actor_type="USER", actor_id=command.actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action=action, outcome="SUCCESS",
            target_owner_module="document", target_object_type="DOC-03",
            target_object_id=command.upload_id,
            before_state="CLEANUP_PENDING",
            after_state="CLEANUP_PENDING" if action == _REQUESTED else "REMOVED",
            reason_code="OBSERVED_ABSENT" if action == _ABSENT else None,
        )

    @staticmethod
    def _validate(command: CleanupRegisteredAbort) -> None:
        if (type(command) is not CleanupRegisteredAbort
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.upload_id, command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or (command.scope == "GLOBAL" and command.project_id is not None)
                or (command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0))):
            raise RegisteredAbortCleanupError("VALIDATION_FAILED")
