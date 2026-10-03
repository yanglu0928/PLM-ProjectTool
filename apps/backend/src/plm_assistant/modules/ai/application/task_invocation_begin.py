"""Atomically persist a PENDING AI Invocation from a current execution grant."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .task_execution_grant import (
    AITaskExecutionGrant,
    AITaskExecutionGrantError,
    AITaskPayloadPlanProof,
    require_payload_plan,
)
from .task_execution_grant_service import AITaskExecutionGrantIssuer


class AITaskInvocationBeginError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_INVOCATION_NOT_STARTED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BegunAITaskInvocation:
    ai_invocation_id: uuid.UUID
    grant: AITaskExecutionGrant

    def __post_init__(self) -> None:
        if (type(self.ai_invocation_id) is not uuid.UUID
                or not self.ai_invocation_id.int
                or type(self.grant) is not AITaskExecutionGrant):
            raise AITaskInvocationBeginError()
        self.grant.__post_init__()


class AITaskInvocationBeginRepositoryPort(Protocol):
    def begin(self, transaction: object, *, grant: AITaskExecutionGrant,
              now: datetime) -> uuid.UUID: ...


class AITaskInvocationBeginService:
    """Grant, INSERT and Task pointer update share one short transaction."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 grants: AITaskExecutionGrantIssuer,
                 repository: AITaskInvocationBeginRepositoryPort) -> None:
        if any(value is None for value in (unit_of_work, grants, repository)):
            raise ValueError("AI Task Invocation begin dependencies required")
        self._uow = unit_of_work
        self._grants = grants
        self._repository = repository

    def begin(self, *, job_id: uuid.UUID, fencing_token: int,
              worker_ref: str, now: datetime,
              payload_plan: AITaskPayloadPlanProof) -> BegunAITaskInvocation:
        if (type(job_id) is not uuid.UUID or not job_id.int
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None
                or type(payload_plan) is not AITaskPayloadPlanProof):
            raise AITaskInvocationBeginError()
        now = now.astimezone(timezone.utc)
        try:
            with self._uow() as transaction:
                grant = self._grants.issue_in(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref, now=now,
                )
                require_payload_plan(grant, payload_plan, now=now)
                invocation_id = self._repository.begin(
                    transaction, grant=grant, now=now,
                )
                result = BegunAITaskInvocation(invocation_id, grant)
                transaction.commit()
            self._grants.require_usable(grant)
            return result
        except AITaskInvocationBeginError:
            raise
        except AITaskExecutionGrantError:
            raise AITaskInvocationBeginError() from None
        except Exception:
            raise AITaskInvocationBeginError() from None
