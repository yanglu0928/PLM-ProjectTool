"""AI-owned cancellation core across the durable Provider send boundary."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService


class AITaskCancellationError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_CANCEL_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CancelAITaskExecution:
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    expected_version: int
    reason: str = field(repr=False)

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.ai_task_id, self.project_id, self.requested_by,
                self.trace_id))
                or type(self.expected_version) is not int
                or not 0 <= self.expected_version <= 9_223_372_036_854_775_807
                or type(self.reason) is not str
                or not 1 <= len(self.reason) <= 1024
                or self.reason.strip() != self.reason
                or any(unicodedata.category(char).startswith("C")
                       for char in self.reason)):
            raise AITaskCancellationError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class CancelledAITaskExecution:
    ai_task_id: uuid.UUID
    ai_invocation_id: uuid.UUID | None
    job_id: uuid.UUID
    project_id: uuid.UUID
    state: str
    changed: bool
    crossed_send_fence: bool
    error_code: str | None
    lock_version: int
    job_lock_version: int
    completed_at: datetime | None

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.ai_task_id, self.job_id, self.project_id))
                or (self.ai_invocation_id is not None
                    and (type(self.ai_invocation_id) is not uuid.UUID
                         or not self.ai_invocation_id.int))
                or self.state not in {"CANCELLED", "SUCCEEDED", "FAILED"}
                or type(self.changed) is not bool
                or type(self.crossed_send_fence) is not bool
                or (self.crossed_send_fence
                    and (self.state != "FAILED"
                         or self.error_code != "AI_PROVIDER_OUTCOME_UNKNOWN"))
                or type(self.lock_version) is not int or self.lock_version < 0
                or type(self.job_lock_version) is not int
                or self.job_lock_version < 0
                or (self.completed_at is not None
                    and (not isinstance(self.completed_at, datetime)
                         or self.completed_at.tzinfo is None
                         or self.completed_at.utcoffset() is None))):
            raise AITaskCancellationError()


class AITaskCancellationStorePort(Protocol):
    def cancel(
        self, transaction: object, *, command: CancelAITaskExecution,
    ) -> CancelledAITaskExecution: ...


class AITaskCancellationOwner:
    """Authorization is a required upstream port; this owner controls state mutation."""

    def __init__(
        self, *, unit_of_work: Callable[[], object],
        store: AITaskCancellationStorePort, audit: AuditService,
    ) -> None:
        if any(value is None for value in (unit_of_work, store, audit)):
            raise ValueError("AI Task cancellation dependencies required")
        self._uow = unit_of_work
        self._store = store
        self._audit = audit

    def cancel(self, command: CancelAITaskExecution) -> CancelledAITaskExecution:
        if type(command) is not CancelAITaskExecution:
            raise AITaskCancellationError("VALIDATION_FAILED")
        command.__post_init__()
        try:
            with self._uow() as transaction:
                result, _ = self.cancel_in_transaction(transaction, command)
                transaction.commit()
            return result
        except AITaskCancellationError:
            raise
        except Exception:
            raise AITaskCancellationError() from None

    def cancel_in_transaction(
        self, transaction: object, command: CancelAITaskExecution,
    ) -> tuple[CancelledAITaskExecution, uuid.UUID]:
        """Mutate and append Audit inside a caller-owned transaction."""
        if type(command) is not CancelAITaskExecution:
            raise AITaskCancellationError("VALIDATION_FAILED")
        command.__post_init__()
        result = self._store.cancel(transaction, command=command)
        if (type(result) is not CancelledAITaskExecution
                or result.ai_task_id != command.ai_task_id
                or result.project_id != command.project_id):
            raise AITaskCancellationError()
        result.__post_init__()
        if result.crossed_send_fence:
            action, outcome, reason_code = (
                "AI_TASK_CANCEL_OUTCOME_UNKNOWN", "FAILED",
                "AI_PROVIDER_OUTCOME_UNKNOWN",
            )
        elif result.changed:
            action, outcome, reason_code = (
                "AI_TASK_CANCELLED", "SUCCESS", "USER_REQUESTED",
            )
        else:
            action, outcome, reason_code = (
                "AI_TASK_CANCEL_CHECKED", "SUCCESS", "USER_REQUESTED",
            )
        event_id = self._audit.append(transaction, AuditEventDraft(
            trace_id=command.trace_id, event_scope="PROJECT",
            target_project_id=command.project_id,
            actor_type="USER", actor_id=command.requested_by,
            original_actor_id=None, actor_hint_digest=None,
            action=action, outcome=outcome,
            target_owner_module="ai", target_object_type="AI-04",
            target_object_id=command.ai_task_id,
            target_version_id=result.ai_invocation_id,
            reason_code=reason_code,
            before_state=(
                result.state
                if not result.changed
                else ("RUNNING" if result.ai_invocation_id is not None
                      else "QUEUED")
            ),
            after_state=result.state,
        ))
        if type(event_id) is not uuid.UUID or not event_id.int:
            raise AITaskCancellationError()
        return result, event_id
