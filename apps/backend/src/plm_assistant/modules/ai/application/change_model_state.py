"""Authorized non-AVAILABLE AIModel safety transitions with immutable replay."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


_OPERATIONS = {
    "SUSPEND": (frozenset({"AVAILABLE"}), "SUSPENDED", "AI_MODEL_SUSPENDED"),
    "RETIRE": (frozenset({"AVAILABLE", "SUSPENDED"}), "RETIRED", "AI_MODEL_RETIRED"),
}


class AIModelStateError(RuntimeError):
    def __init__(self, code: str = "AI_MODEL_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ChangeAIModelState:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    model_id: uuid.UUID
    expected_lock_version: int
    operation: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AIModelStateResult:
    result_id: uuid.UUID
    model_id: uuid.UUID
    actor_id: uuid.UUID
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    operation: str
    before_state: str
    state: str
    expected_lock_version: int
    lock_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.result_id, self.model_id, self.actor_id, self.audit_event_id,
                self.trace_id))
                or self.operation not in _OPERATIONS
                or self.before_state not in _OPERATIONS[self.operation][0]
                or self.state != _OPERATIONS[self.operation][1]
                or type(self.expected_lock_version) is not int
                or not 0 <= self.expected_lock_version <= 9223372036854775806
                or type(self.lock_version) is not int
                or self.lock_version != self.expected_lock_version + 1):
            raise AIModelStateError()

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


class _Access(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class _Repository(Protocol):
    def locked_state(self, transaction: object, *, model_id: uuid.UUID) -> tuple[str, int] | None: ...
    def change(self, transaction: object, *, model_id: uuid.UUID, before_state: str,
               state: str, expected_lock_version: int) -> int: ...
    def save(self, transaction: object, *, result: AIModelStateResult) -> None: ...
    def get(self, transaction: object, *, result_id: uuid.UUID, model_id: uuid.UUID,
            actor_id: uuid.UUID, operation: str,
            expected_lock_version: int) -> AIModelStateResult | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AIModelStateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: object, repository: _Repository, receipts: _Receipts,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                           repository, receipts, audit)):
            raise ValueError("AI Model state dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def change(self, command: ChangeAIModelState) -> AIModelStateResult:
        if (type(command) is not ChangeAIModelState
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.model_id) is not uuid.UUID or command.model_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806
                or type(command.operation) is not str or command.operation not in _OPERATIONS):
            raise AIModelStateError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "model_id": str(command.model_id), "operation": command.operation,
                "expected_lock_version": command.expected_lock_version,
            })
        except IdempotencyError:
            raise AIModelStateError("VALIDATION_FAILED") from None
        ref_type = f"V1_AI_MODEL_{command.operation}"
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation=ref_type, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != ref_type or replay.status_code != 200:
                        raise AIModelStateError()
                    original = self._repo.get(
                        tx, result_id=replay.ref_id, model_id=command.model_id,
                        actor_id=actor_id, operation=command.operation,
                        expected_lock_version=command.expected_lock_version,
                    )
                    if type(original) is not AIModelStateResult:
                        raise AIModelStateError()
                    original.__post_init__()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return original
                current = self._repo.locked_state(tx, model_id=command.model_id)
                if current is None:
                    raise AIModelStateError("RESOURCE_NOT_FOUND")
                before_state, before_version = current
                if before_version != command.expected_lock_version:
                    raise AIModelStateError("CONFLICT_VERSION")
                allowed, state, action = _OPERATIONS[command.operation]
                if before_state not in allowed:
                    raise AIModelStateError("CONFLICT_STATE")
                changed = self._repo.change(
                    tx, model_id=command.model_id, before_state=before_state,
                    state=state, expected_lock_version=before_version,
                )
                if changed != before_version + 1:
                    raise AIModelStateError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action=action, outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-02",
                    target_object_id=command.model_id,
                    before_state=before_state, after_state=state,
                ))
                result = AIModelStateResult(
                    uuid.UUID(new_uuid7()), command.model_id, actor_id, audit_id,
                    command.trace_id, command.operation, before_state, state,
                    before_version, changed,
                )
                result.__post_init__()
                self._repo.save(tx, result=result)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    ref_type, result.result_id, 200,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except AIModelStateError:
            raise
        except RuntimeLicenseError:
            raise AIModelStateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIModelStateError(exc.code) from None
        except Exception:
            raise AIModelStateError() from None

    def _require_admin(self, tx: object, command: ChangeAIModelState) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIModelStateError()
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise AIModelStateError("AUTH_ACCESS_DENIED")
        return actor_id
