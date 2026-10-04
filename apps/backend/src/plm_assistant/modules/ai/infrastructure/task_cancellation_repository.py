"""PostgreSQL AI Task cancellation at pre/post Provider send checkpoints."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.cancel_task_execution import (
    AITaskCancellationError,
    CancelAITaskExecution,
    CancelledAITaskExecution,
)
from plm_assistant.modules.ai.application.request_task_cancel import (
    AITaskCancellationBinding,
)
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow, AITaskRow
from plm_assistant.modules.jobs.infrastructure.orm import (
    JobAttemptRow,
    JobLeaseRow,
    JobRow,
)


class SqlAlchemyAITaskCancellationRepository:
    def binding(
        self, transaction: object, *, job_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> AITaskCancellationBinding | None:
        session = _session(transaction)
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.job_ref == job_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == project_id,
        ).with_for_update(of=AITaskRow).execution_options(populate_existing=True))
        if task is None:
            return None
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == job_id,
            JobRow.owner_module == "ai",
            JobRow.job_type == "AI_TASK_EXECUTE",
            JobRow.scope == "PROJECT",
            JobRow.project_id == project_id,
            JobRow.actor_ref == task.requested_by,
            JobRow.trace_id == str(task.trace_id),
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        if job is None:
            return None
        return AITaskCancellationBinding(
            task.ai_task_id, job.job_id, project_id, task.requested_by,
            task.lock_version, job.lock_version,
        )

    def receipt(
        self, transaction: object, *, binding: AITaskCancellationBinding,
        actor_id: uuid.UUID, audit_event_id: uuid.UUID,
    ) -> CancelledAITaskExecution:
        session = _session(transaction)
        event = session.scalar(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == audit_event_id,
            AuditEventRow.event_scope == "PROJECT",
            AuditEventRow.target_project_id == binding.project_id,
            AuditEventRow.actor_type == "USER",
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.original_actor_id.is_(None),
            AuditEventRow.action.in_((
                "AI_TASK_CANCELLED", "AI_TASK_CANCEL_CHECKED",
                "AI_TASK_CANCEL_OUTCOME_UNKNOWN",
            )),
            AuditEventRow.target_owner_module == "ai",
            AuditEventRow.target_object_type == "AI-04",
            AuditEventRow.target_object_id == binding.ai_task_id,
        ))
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == binding.ai_task_id,
            AITaskRow.job_ref == binding.job_id,
            AITaskRow.project_id == binding.project_id,
        ))
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == binding.job_id,
            JobRow.owner_module == "ai",
            JobRow.job_type == "AI_TASK_EXECUTE",
            JobRow.project_id == binding.project_id,
        ))
        if (event is None or task is None or job is None
                or task.task_state != job.state
                or event.after_state != task.task_state
                or event.target_version_id != task.current_invocation_ref
                or task.task_state not in {"CANCELLED", "SUCCEEDED", "FAILED"}):
            raise AITaskCancellationError()
        crossed = event.action == "AI_TASK_CANCEL_OUTCOME_UNKNOWN"
        changed = event.action != "AI_TASK_CANCEL_CHECKED"
        if (crossed and (event.outcome != "FAILED"
                        or event.reason_code != "AI_PROVIDER_OUTCOME_UNKNOWN"
                        or task.error_code != "AI_PROVIDER_OUTCOME_UNKNOWN")
                or not crossed and (event.outcome != "SUCCESS"
                                    or event.reason_code != "USER_REQUESTED")):
            raise AITaskCancellationError()
        return CancelledAITaskExecution(
            task.ai_task_id, task.current_invocation_ref, job.job_id,
            binding.project_id, task.task_state, changed, crossed,
            task.error_code, task.lock_version, job.lock_version,
            task.completed_at,
        )

    def cancel(
        self, transaction: object, *, command: CancelAITaskExecution,
    ) -> CancelledAITaskExecution:
        session = _session(transaction)
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == command.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == command.project_id,
        ).with_for_update(of=AITaskRow).execution_options(populate_existing=True))
        if task is None or task.job_ref is None:
            raise AITaskCancellationError("RESOURCE_NOT_FOUND")
        if task.lock_version != command.expected_version:
            raise AITaskCancellationError("CONFLICT_VERSION")
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == task.job_ref,
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        if (job is None
                or (job.owner_module, job.job_type, job.scope, job.project_id,
                    job.actor_ref, job.trace_id) != (
                    "ai", "AI_TASK_EXECUTE", "PROJECT", command.project_id,
                    task.requested_by, str(task.trace_id))):
            raise AITaskCancellationError("RESOURCE_NOT_FOUND")
        invocation = None
        if task.current_invocation_ref is not None:
            invocation = session.scalar(select(AIInvocationRow).where(
                AIInvocationRow.ai_invocation_id == task.current_invocation_ref,
                AIInvocationRow.ai_task_id == task.ai_task_id,
                AIInvocationRow.scope == "PROJECT",
                AIInvocationRow.project_id == command.project_id,
            ).with_for_update(of=AIInvocationRow).execution_options(
                populate_existing=True,
            ))
            if invocation is None:
                raise AITaskCancellationError()
        if task.task_state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            if job.state != task.task_state:
                raise AITaskCancellationError()
            return CancelledAITaskExecution(
                task.ai_task_id,
                None if invocation is None else invocation.ai_invocation_id,
                job.job_id, command.project_id, task.task_state, False,
                False, task.error_code, task.lock_version, job.lock_version,
                task.completed_at,
            )
        if (task.task_state not in {"QUEUED", "RUNNING"}
                or job.state not in {"PENDING", "RETRY_WAIT", "RUNNING"}
                or task.suggestion_state != "NONE"
                or task.completed_at is not None or job.completed_at is not None):
            raise AITaskCancellationError("AI_TASK_STATE_INVALID")
        now = session.scalar(select(func.clock_timestamp()))
        lease = attempt = None
        if job.state == "RUNNING":
            lease = session.scalar(select(JobLeaseRow).where(
                JobLeaseRow.job_id == job.job_id,
                JobLeaseRow.fencing_token == job.fencing_token,
            ).with_for_update(of=JobLeaseRow).execution_options(populate_existing=True))
            attempt = session.scalar(select(JobAttemptRow).where(
                JobAttemptRow.job_id == job.job_id,
                JobAttemptRow.fencing_token == job.fencing_token,
            ).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
            if (lease is None or attempt is None or lease.state != "ACTIVE"
                    or lease.worker_ref != attempt.worker_ref
                    or lease.lease_expires_at != job.lease_expires_at
                    or lease.lease_expires_at <= now
                    or attempt.attempt_no != job.attempt_count
                    or attempt.completed_at is not None
                    or attempt.error_code is not None):
                raise AITaskCancellationError("AI_TASK_STATE_INVALID")
        elif (job.lease_expires_at is not None
              or session.scalar(select(JobLeaseRow.lease_id).where(
                  JobLeaseRow.job_id == job.job_id,
                  JobLeaseRow.state == "ACTIVE",
              ).with_for_update(of=JobLeaseRow)) is not None):
            raise AITaskCancellationError()

        crossed = invocation is not None and invocation.invocation_state == "RUNNING"
        if invocation is not None and invocation.invocation_state not in {
                "PENDING", "RUNNING"}:
            raise AITaskCancellationError("AI_TASK_STATE_INVALID")
        if crossed:
            state, error_code, retryable = (
                "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", False,
            )
        else:
            state, error_code, retryable = "CANCELLED", None, None
            job.cancel_requested_by = command.requested_by
            job.cancel_requested_at = now
            job.cancel_reason = command.reason
        job.state = state
        job.completed_at = now
        job.lease_expires_at = None
        if lease is not None and attempt is not None:
            lease.state = "RELEASED"
            attempt.completed_at = now
            attempt.error_code = (
                "AI_PROVIDER_OUTCOME_UNKNOWN" if crossed else "JOB_CANCELLED"
            )
        if invocation is not None:
            if invocation.started_at is None:
                invocation.started_at = now
            invocation.invocation_state = state
            invocation.error_code = error_code
            invocation.retryable = retryable
            invocation.completed_at = now
            invocation.lock_version += 1
        if task.started_at is None:
            task.started_at = now
        task.task_state = state
        task.error_code = error_code
        task.retryable = retryable
        task.completed_at = now
        task.lock_version += 1
        session.flush()
        session.refresh(job, attribute_names=("lock_version",))
        return CancelledAITaskExecution(
            task.ai_task_id,
            None if invocation is None else invocation.ai_invocation_id,
            job.job_id, command.project_id, state, True, crossed,
            error_code, task.lock_version, job.lock_version, now,
        )
