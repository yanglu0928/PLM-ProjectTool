"""Reconcile one expired AI execution without reviving or resending it."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService


class AITaskReconciliationError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_RECONCILIATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReconciledAITaskFailure:
    ai_task_id: uuid.UUID
    ai_invocation_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    prior_invocation_state: str
    error_code: str
    retryable: bool
    completed_at: datetime

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.ai_task_id, self.ai_invocation_id, self.job_id,
                self.project_id, self.requested_by, self.trace_id))
                or self.prior_invocation_state not in {"PENDING", "RUNNING"}
                or type(self.error_code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None
                or type(self.retryable) is not bool
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise AITaskReconciliationError()


class AITaskReconciliationStorePort(Protocol):
    def reconcile_next(
        self, transaction: object,
    ) -> ReconciledAITaskFailure | None: ...


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class ExpiredAITaskReconciler:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        store: AITaskReconciliationStorePort, audit: AuditService,
        system_actor: _SystemActor,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, store, audit, system_actor)):
            raise ValueError("AI Task reconciliation dependencies required")
        self._uow = unit_of_work
        self._store = store
        self._audit = audit
        self._actor = system_actor

    def reconcile_next(self) -> ReconciledAITaskFailure | None:
        try:
            actor_id = self._actor.assert_current()
            if type(actor_id) is not uuid.UUID or not actor_id.int:
                raise AITaskReconciliationError("SYSTEM_ACTOR_UNAVAILABLE")
            with self._uow() as transaction:
                result = self._store.reconcile_next(transaction)
                if result is None:
                    return None
                if type(result) is not ReconciledAITaskFailure:
                    raise AITaskReconciliationError()
                result.__post_init__()
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=result.trace_id, event_scope="PROJECT",
                    target_project_id=result.project_id,
                    actor_type="SYSTEM", actor_id=actor_id,
                    original_actor_id=result.requested_by,
                    actor_hint_digest=None,
                    action="AI_TASK_EXECUTION_RECONCILED", outcome="FAILED",
                    target_owner_module="ai", target_object_type="AI-04",
                    target_object_id=result.ai_task_id,
                    target_version_id=result.ai_invocation_id,
                    reason_code=result.error_code,
                    before_state="RUNNING", after_state="FAILED",
                ))
                if (type(event_id) is not uuid.UUID or not event_id.int
                        or self._actor.assert_current() != actor_id):
                    raise AITaskReconciliationError()
                transaction.commit()
            return result
        except AITaskReconciliationError:
            raise
        except Exception:
            raise AITaskReconciliationError() from None
