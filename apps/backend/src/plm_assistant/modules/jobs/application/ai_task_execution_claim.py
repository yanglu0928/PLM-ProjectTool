"""Jobs-owned current lease proof for one AI Task execution attempt."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint


@dataclass(frozen=True, slots=True)
class AITaskExecutionClaim:
    job_id: uuid.UUID
    ai_task_id: uuid.UUID
    project_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    egress_authorization_ref: uuid.UUID
    input_fingerprint: bytes = field(repr=False)
    fencing_token: int = 0
    attempt_no: int = 0
    max_attempts: int = 0
    observed_at: datetime | None = None
    lease_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.job_id, self.ai_task_id, self.project_id, self.actor_id,
                self.trace_id, self.egress_authorization_ref,
            ))
                or type(self.input_fingerprint) is not bytes
                or len(self.input_fingerprint) != 32
                or type(self.fencing_token) is not int
                or not 1 <= self.fencing_token <= 9_223_372_036_854_775_807
                or type(self.attempt_no) is not int
                or type(self.max_attempts) is not int
                or not 1 <= self.attempt_no <= self.max_attempts <= 10
                or not isinstance(self.observed_at, datetime)
                or self.observed_at.tzinfo is None
                or self.observed_at.utcoffset() is None
                or not isinstance(self.lease_expires_at, datetime)
                or self.lease_expires_at.tzinfo is None
                or self.lease_expires_at.utcoffset() is None
                or self.observed_at >= self.lease_expires_at):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")


class AITaskExecutionClaimRepositoryPort(Protocol):
    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int,
                      worker_ref: str) -> AITaskExecutionClaim: ...


class AITaskExecutionClaims:
    """Validate a Jobs-owned proof inside the caller's short transaction."""

    def __init__(self, *, repository: AITaskExecutionClaimRepositoryPort) -> None:
        if repository is None:
            raise ValueError("AI Task execution claim repository required")
        self._repository = repository

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> AITaskExecutionClaim:
        validate_checkpoint(
            job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref,
        )
        try:
            claim = self._repository.check_current(
                transaction, job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref,
            )
            if (type(claim) is not AITaskExecutionClaim
                    or claim.job_id != job_id
                    or claim.fencing_token != fencing_token):
                raise JobLeaseError("JOB_STORE_UNAVAILABLE")
            claim.__post_init__()
            return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
