"""Read-only eligibility proof for a registered aborted upload; never deletes."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.document.application.upload_operation_gate import (
    UploadGateUnavailable, UploadOperationGatePort,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalStorageError


class RegisteredAbortInspectionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("registered abort inspection unavailable")


@dataclass(frozen=True, slots=True)
class RegisteredAbortCandidate:
    upload_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    staging_locator: str = field(repr=False)
    final_locator: str = field(repr=False)
    sha256: bytes = field(repr=False)
    size_bytes: int
    file_lock_version: int
    intent_lock_version: int


@dataclass(frozen=True, slots=True)
class RegisteredAbortInspection:
    upload_id: uuid.UUID
    shape: str
    eligible: bool


class RegisteredAbortReadPort(Protocol):
    def candidate(self, transaction: object, upload_id: uuid.UUID) -> RegisteredAbortCandidate | None: ...


class RegisteredAbortStoragePort(Protocol):
    def inspect_recovery(self, staging_locator: str, final_locator: str, *,
                         expected_sha256: bytes, expected_size: int,
                         max_bytes: int) -> object: ...

    def verify_content(self, locator: str, *, expected_sha256: bytes,
                       expected_size: int, max_bytes: int) -> object: ...


class InspectRegisteredAbortService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: RegisteredAbortReadPort, storage: RegisteredAbortStoragePort,
                 operation_gate: UploadOperationGatePort) -> None:
        if any(item is None for item in (unit_of_work, repository, storage, operation_gate)):
            raise ValueError("registered abort inspection dependencies are required")
        self._uow, self._repository = unit_of_work, repository
        self._storage, self._gate = storage, operation_gate

    def inspect(self, upload_id: uuid.UUID) -> RegisteredAbortInspection:
        if type(upload_id) is not uuid.UUID or upload_id.int == 0:
            raise RegisteredAbortInspectionError()
        try:
            with self._gate.hold(upload_id):
                with self._uow() as tx:
                    candidate = self._repository.candidate(tx, upload_id)
                if candidate is None:
                    return RegisteredAbortInspection(upload_id, "DB_INELIGIBLE", False)
                physical = self._storage.inspect_recovery(
                    candidate.staging_locator, candidate.final_locator,
                    expected_sha256=candidate.sha256,
                    expected_size=candidate.size_bytes, max_bytes=100_000_000,
                )
                shape = physical.shape
                if shape != "STAGE_ONLY":
                    return RegisteredAbortInspection(upload_id, shape, False)
                try:
                    self._storage.verify_content(
                        candidate.staging_locator,
                        expected_sha256=candidate.sha256,
                        expected_size=candidate.size_bytes, max_bytes=100_000_000,
                    )
                except LocalStorageError:
                    return RegisteredAbortInspection(upload_id, "STAGE_INVALID", False)
                with self._uow() as tx:
                    current = self._repository.candidate(tx, upload_id)
                if current != candidate:
                    return RegisteredAbortInspection(upload_id, "DB_CHANGED", False)
                return RegisteredAbortInspection(upload_id, "STAGE_VERIFIED", True)
        except (UploadGateUnavailable, LocalStorageError):
            raise RegisteredAbortInspectionError() from None
