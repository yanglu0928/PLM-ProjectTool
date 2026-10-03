"""PostgreSQL atomic AI Invocation and Task failure terminalization."""

from __future__ import annotations

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.publish_task_failure import (
    AITaskFailurePhase,
    PublishedAITaskFailure,
)
from plm_assistant.modules.ai.application.task_invocation_begin import BegunAITaskInvocation
from plm_assistant.modules.ai.application.task_invocation_prepare import PreparedAITaskInvocation
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow, AITaskRow


class SqlAlchemyAITaskFailureRepository:
    def publish(
        self, transaction: object, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, phase: AITaskFailurePhase,
        error_code: str, retryable: bool,
        response_fingerprint: bytes | None,
    ) -> PublishedAITaskFailure:
        session = _session(transaction)
        grant = prepared.grant
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == grant.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == grant.project_id,
            AITaskRow.job_ref == grant.job_id,
            AITaskRow.requested_by == grant.requested_by,
            AITaskRow.trace_id == grant.trace_id,
            AITaskRow.content_plan_ref == grant.content_plan_id,
            AITaskRow.task_state == "RUNNING",
            AITaskRow.suggestion_state == "NONE",
            AITaskRow.current_invocation_ref == begun.ai_invocation_id,
            AITaskRow.completed_at.is_(None),
            AITaskRow.error_code.is_(None),
            AITaskRow.retryable.is_(None),
        ).with_for_update().execution_options(autoflush=False))
        expected_state = (
            "PENDING" if phase is AITaskFailurePhase.PRE_SEND else "RUNNING"
        )
        invocation = session.scalar(select(AIInvocationRow).where(
            AIInvocationRow.ai_invocation_id == begun.ai_invocation_id,
            AIInvocationRow.ai_task_id == grant.ai_task_id,
            AIInvocationRow.attempt_no == grant.attempt_no,
            AIInvocationRow.scope == "PROJECT",
            AIInvocationRow.project_id == grant.project_id,
            AIInvocationRow.content_plan_ref == grant.content_plan_id,
            AIInvocationRow.invocation_state == expected_state,
            AIInvocationRow.completed_at.is_(None),
            AIInvocationRow.suggestion_payload_ref.is_(None),
            AIInvocationRow.response_fingerprint.is_(None),
            AIInvocationRow.error_code.is_(None),
            AIInvocationRow.retryable.is_(None),
            AIInvocationRow.schema_validation_required.is_(True),
            AIInvocationRow.schema_validation_state == "PENDING",
        ).with_for_update().execution_options(autoflush=False))
        if task is None or invocation is None:
            raise RuntimeError("AI Task failure state mismatch")
        completed_at = session.scalar(select(func.clock_timestamp()))
        if invocation.started_at is None:
            invocation.started_at = completed_at
        invocation.invocation_state = "FAILED"
        invocation.schema_validation_state = (
            "INVALID" if phase is AITaskFailurePhase.RESPONSE_INVALID
            else "PENDING"
        )
        invocation.response_fingerprint = response_fingerprint
        invocation.error_code = error_code
        invocation.retryable = retryable
        invocation.completed_at = completed_at
        invocation.lock_version += 1
        task.task_state = "FAILED"
        task.error_code = error_code
        task.retryable = retryable
        task.completed_at = completed_at
        task.lock_version += 1
        session.flush()
        return PublishedAITaskFailure(
            error_code, retryable, phase, completed_at,
        )
