"""PostgreSQL terminalization for a claimed AI Task before Invocation Begin."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.publish_pre_begin_failure import (
    PublishedAITaskPreBeginFailure,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow, AITaskRow
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.jobs.infrastructure.orm import JobRow


class SqlAlchemyAITaskPreBeginFailureRepository:
    def publish(self, transaction: object, *, claim: ClaimedJob,
                error_code: str,
                retryable: bool) -> PublishedAITaskPreBeginFailure:
        session = _session(transaction)
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == claim.job_id, JobRow.owner_module == "ai",
            JobRow.job_type == "AI_TASK_EXECUTE", JobRow.scope == "PROJECT",
            JobRow.project_id == claim.project_id, JobRow.state == "FAILED",
            JobRow.fencing_token == claim.fencing_token,
            JobRow.attempt_count == claim.attempt_no,
            JobRow.lease_expires_at.is_(None), JobRow.completed_at.is_not(None),
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        if job is None or type(job.payload_refs) is not dict:
            raise RuntimeError("AI Task pre-Begin Job mismatch")
        try:
            task_id = uuid.UUID(job.payload_refs["ai_task_id"])
            trace_id = uuid.UUID(job.trace_id)
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("AI Task pre-Begin identity mismatch") from None
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == task_id,
            AITaskRow.job_ref == job.job_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == job.project_id,
            AITaskRow.trace_id == trace_id,
            AITaskRow.task_state == "QUEUED",
            AITaskRow.suggestion_state == "NONE",
            AITaskRow.current_invocation_ref.is_(None),
            AITaskRow.started_at.is_(None), AITaskRow.completed_at.is_(None),
            AITaskRow.error_code.is_(None), AITaskRow.retryable.is_(None),
        ).with_for_update(of=AITaskRow).execution_options(populate_existing=True))
        invocation = session.scalar(select(AIInvocationRow.ai_invocation_id).where(
            AIInvocationRow.ai_task_id == task_id,
        ).limit(1))
        if (task is None or invocation is not None
                or claim.payload_refs != job.payload_refs
                or claim.trace_id != job.trace_id
                or job.project_id is None
                or job.actor_ref != task.requested_by):
            raise RuntimeError("AI Task pre-Begin state mismatch")
        completed_at = session.scalar(select(func.clock_timestamp()))
        task.task_state = "FAILED"
        task.started_at = completed_at
        task.completed_at = completed_at
        task.error_code = error_code
        task.retryable = retryable
        task.lock_version += 1
        session.flush()
        return PublishedAITaskPreBeginFailure(
            task.ai_task_id, job.job_id, job.project_id, task.requested_by,
            trace_id, error_code, retryable, completed_at,
        )
