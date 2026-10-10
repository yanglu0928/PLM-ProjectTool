"""Same-transaction AI Task/Job read proof."""

from __future__ import annotations

from sqlalchemy import select

from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AITaskRow
from plm_assistant.modules.jobs.application.authorized_read import JobReadError, JobReadFacts
from plm_assistant.modules.jobs.infrastructure.orm import JobRow

_VALID_TASK_JOB_STATE_PAIRS = frozenset({
    ("QUEUED", "PENDING"),
    ("RUNNING", "RUNNING"),
    ("SUCCEEDED", "SUCCEEDED"),
    ("FAILED", "FAILED"),
    ("CANCEL_REQUESTED", "CANCEL_REQUESTED"),
    ("CANCELLED", "CANCELLED"),
})


class SqlAlchemyAITaskJobReadRepository:
    def retryable(self, transaction: object, *, facts: JobReadFacts) -> bool:
        session = _session(transaction)
        row = session.execute(select(AITaskRow, JobRow).join(
            JobRow, JobRow.job_id == AITaskRow.job_ref,
        ).where(
            JobRow.job_id == facts.job_id,
            JobRow.owner_module == "ai", JobRow.job_type == "AI_TASK_EXECUTE",
            AITaskRow.scope == "PROJECT", AITaskRow.project_id == facts.project_id,
        ).execution_options(autoflush=False)).one_or_none()
        if row is None:
            raise JobReadError("RESOURCE_NOT_FOUND")
        task, job = row
        if ((job.job_id, job.owner_module, job.job_type, job.scope,
             job.project_id, job.actor_ref, job.state, job.attempt_count,
             job.lock_version) !=
                (facts.job_id, facts.owner_module, facts.job_type, facts.scope,
                 facts.project_id, facts.actor_id, facts.state,
                 facts.attempt_count, facts.lock_version)
                or (task.task_state, job.state) not in _VALID_TASK_JOB_STATE_PAIRS
                or task.suggestion_state != "NONE"):
            raise JobReadError()
        return (task.task_state == "CANCELLED"
                or task.task_state == "FAILED" and task.retryable is True)
