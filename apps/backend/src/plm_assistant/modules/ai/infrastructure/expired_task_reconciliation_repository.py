"""PostgreSQL owner for expired AI Task Job/Invocation reconciliation."""

from __future__ import annotations

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.reconcile_expired_task import (
    ReconciledAITaskFailure,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow, AITaskRow
from plm_assistant.modules.jobs.infrastructure.orm import (
    JobAttemptRow,
    JobLeaseRow,
    JobRow,
)


class SqlAlchemyExpiredAITaskReconciliationRepository:
    def reconcile_next(self, transaction: object) -> ReconciledAITaskFailure | None:
        session = _session(transaction)
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(JobRow).where(
            JobRow.owner_module == "ai",
            JobRow.job_type == "AI_TASK_EXECUTE",
            JobRow.scope == "PROJECT",
            JobRow.state == "RUNNING",
            JobRow.lease_expires_at.is_not(None),
            JobRow.lease_expires_at <= now,
        ).order_by(JobRow.lease_expires_at, JobRow.job_id).limit(1)
            .with_for_update(of=JobRow, skip_locked=True)
            .execution_options(populate_existing=True))
        if job is None:
            return None
        lease = session.scalar(select(JobLeaseRow).where(
            JobLeaseRow.job_id == job.job_id,
            JobLeaseRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobLeaseRow).execution_options(populate_existing=True))
        attempt = session.scalar(select(JobAttemptRow).where(
            JobAttemptRow.job_id == job.job_id,
            JobAttemptRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.job_ref == job.job_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == job.project_id,
            AITaskRow.task_state == "RUNNING",
            AITaskRow.suggestion_state == "NONE",
            AITaskRow.current_invocation_ref.is_not(None),
            AITaskRow.completed_at.is_(None),
            AITaskRow.error_code.is_(None),
            AITaskRow.retryable.is_(None),
        ).with_for_update(of=AITaskRow).execution_options(populate_existing=True))
        invocation = None if task is None else session.scalar(select(
            AIInvocationRow,
        ).where(
            AIInvocationRow.ai_invocation_id == task.current_invocation_ref,
            AIInvocationRow.ai_task_id == task.ai_task_id,
            AIInvocationRow.attempt_no == job.attempt_count,
            AIInvocationRow.scope == "PROJECT",
            AIInvocationRow.project_id == job.project_id,
            AIInvocationRow.invocation_state.in_(("PENDING", "RUNNING")),
            AIInvocationRow.completed_at.is_(None),
            AIInvocationRow.suggestion_payload_ref.is_(None),
            AIInvocationRow.response_fingerprint.is_(None),
            AIInvocationRow.error_code.is_(None),
            AIInvocationRow.retryable.is_(None),
        ).with_for_update(of=AIInvocationRow).execution_options(
            populate_existing=True,
        ))
        if (lease is None or attempt is None or task is None or invocation is None
                or job.project_id is None or job.actor_ref != task.requested_by
                or job.trace_id != str(task.trace_id)
                or job.completed_at is not None
                or not 1 <= job.attempt_count <= job.max_attempts
                or lease.state != "ACTIVE"
                or lease.worker_ref != attempt.worker_ref
                or lease.fencing_token != attempt.fencing_token
                or lease.lease_expires_at != job.lease_expires_at
                or lease.lease_expires_at > now
                or attempt.attempt_no != job.attempt_count
                or attempt.completed_at is not None
                or attempt.error_code is not None):
            raise RuntimeError("inconsistent expired AI Task generation")
        prior_state = invocation.invocation_state
        if prior_state == "RUNNING":
            error_code, retryable = "AI_PROVIDER_OUTCOME_UNKNOWN", False
        else:
            error_code, retryable = "AI_WORKER_LEASE_EXPIRED", True
            invocation.started_at = now
        lease.state = "EXPIRED"
        attempt.completed_at = now
        attempt.error_code = error_code
        job.state = "FAILED"
        job.lease_expires_at = None
        job.completed_at = now
        invocation.invocation_state = "FAILED"
        invocation.error_code = error_code
        invocation.retryable = retryable
        invocation.completed_at = now
        invocation.lock_version += 1
        task.task_state = "FAILED"
        task.error_code = error_code
        task.retryable = retryable
        task.completed_at = now
        task.lock_version += 1
        session.flush()
        return ReconciledAITaskFailure(
            task.ai_task_id, invocation.ai_invocation_id, job.job_id,
            job.project_id, task.requested_by, task.trace_id,
            prior_state, error_code, retryable, now,
        )
