"""Atomically close a claimed AI Task that cannot prepare an Invocation."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint


class AITaskPreBeginFailureError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_PRE_BEGIN_FAILURE_NOT_PUBLISHED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PublishedAITaskPreBeginFailure:
    ai_task_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    error_code: str
    retryable: bool
    completed_at: datetime

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.ai_task_id, self.job_id, self.project_id,
                self.requested_by, self.trace_id,
            )) or type(self.error_code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None
                or type(self.retryable) is not bool
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise AITaskPreBeginFailureError()


class AITaskPreBeginFailurePublisher:
    def __init__(self, *, unit_of_work, store, jobs, audit, system_actor) -> None:
        if any(value is None for value in (
                unit_of_work, store, jobs, audit, system_actor)):
            raise ValueError("AI Task pre-Begin failure dependencies required")
        self._uow, self._store, self._jobs = unit_of_work, store, jobs
        self._audit, self._actor = audit, system_actor

    def publish(self, *, claim: ClaimedJob, worker_ref: str,
                error_code: str, retryable: bool) -> PublishedAITaskPreBeginFailure:
        if (type(claim) is not ClaimedJob
                or (claim.job_type, claim.scope) != ("AI_TASK_EXECUTE", "PROJECT")
                or claim.project_id is None
                or type(error_code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", error_code) is None
                or type(retryable) is not bool):
            raise AITaskPreBeginFailureError()
        try:
            validate_checkpoint(job_id=claim.job_id,
                                fencing_token=claim.fencing_token,
                                worker_ref=worker_ref)
            actor_id = self._actor.assert_current()
            if type(actor_id) is not uuid.UUID or not actor_id.int:
                raise AITaskPreBeginFailureError()
            with self._uow() as tx:
                state = self._jobs.retry_or_fail(
                    tx, job_id=claim.job_id, fencing_token=claim.fencing_token,
                    worker_ref=worker_ref, error_code=error_code,
                    retryable=False, delay_seconds=0,
                )
                if state != "FAILED":
                    raise AITaskPreBeginFailureError()
                result = self._store.publish(
                    tx, claim=claim, error_code=error_code,
                    retryable=retryable,
                )
                if type(result) is not PublishedAITaskPreBeginFailure:
                    raise AITaskPreBeginFailureError()
                result.__post_init__()
                event_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=result.trace_id, event_scope="PROJECT",
                    target_project_id=result.project_id, actor_type="SYSTEM",
                    actor_id=actor_id, original_actor_id=result.requested_by,
                    actor_hint_digest=None,
                    action="AI_TASK_PREPARATION_FAILED", outcome="FAILED",
                    target_owner_module="ai", target_object_type="AI-04",
                    target_object_id=result.ai_task_id,
                    reason_code=error_code, before_state="QUEUED",
                    after_state="FAILED",
                ))
                if (type(event_id) is not uuid.UUID or not event_id.int
                        or self._actor.assert_current() != actor_id):
                    raise AITaskPreBeginFailureError()
                tx.commit()
            return result
        except AITaskPreBeginFailureError:
            raise
        except JobLeaseError:
            raise AITaskPreBeginFailureError("AI_TASK_JOB_LEASE_LOST") from None
        except Exception:
            raise AITaskPreBeginFailureError() from None
