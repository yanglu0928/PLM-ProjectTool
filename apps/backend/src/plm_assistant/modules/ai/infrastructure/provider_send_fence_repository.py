"""PostgreSQL durable send fence for one current AI Invocation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update

from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AuthorizedAIProviderSend,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    BegunAITaskInvocation,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    PreparedAITaskInvocation,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow, AITaskRow
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
)


class SqlAlchemyAITaskProviderSendFenceRepository:
    def mark_running(
        self, transaction: object, *, claim: AITaskExecutionClaim,
        prepared: PreparedAITaskInvocation, begun: BegunAITaskInvocation,
        send: AuthorizedAIProviderSend, started_at: datetime,
    ) -> int | None:
        session = _session(transaction)
        grant = prepared.grant
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == claim.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == claim.project_id,
            AITaskRow.job_ref == claim.job_id,
            AITaskRow.requested_by == claim.actor_id,
            AITaskRow.trace_id == claim.trace_id,
            AITaskRow.input_fingerprint == claim.input_fingerprint,
            AITaskRow.content_plan_ref == grant.content_plan_id,
            AITaskRow.task_state == "RUNNING",
            AITaskRow.current_invocation_ref == begun.ai_invocation_id,
            AITaskRow.started_at.is_not(None),
            AITaskRow.completed_at.is_(None),
        ).with_for_update().execution_options(autoflush=False))
        if task is None:
            return None
        changed = session.execute(update(AIInvocationRow).where(
            AIInvocationRow.ai_invocation_id == begun.ai_invocation_id,
            AIInvocationRow.ai_task_id == claim.ai_task_id,
            AIInvocationRow.attempt_no == claim.attempt_no,
            AIInvocationRow.scope == "PROJECT",
            AIInvocationRow.project_id == claim.project_id,
            AIInvocationRow.egress_authorization_snapshot_id
            == grant.egress_snapshot_id,
            AIInvocationRow.content_plan_ref == grant.content_plan_id,
            AIInvocationRow.request_payload_fingerprint
            == send.proof.payload_fingerprint,
            AIInvocationRow.invocation_state == "PENDING",
            AIInvocationRow.started_at.is_(None),
            AIInvocationRow.completed_at.is_(None),
            AIInvocationRow.suggestion_payload_ref.is_(None),
            AIInvocationRow.response_fingerprint.is_(None),
            AIInvocationRow.error_code.is_(None),
            AIInvocationRow.retryable.is_(None),
            AIInvocationRow.schema_validation_required.is_(True),
            AIInvocationRow.schema_validation_state == "PENDING",
        ).values(
            invocation_state="RUNNING",
            started_at=started_at,
            lock_version=AIInvocationRow.lock_version + 1,
        ).returning(AIInvocationRow.lock_version).execution_options(
            synchronize_session=False,
        )).one_or_none()
        if changed is None:
            return None
        session.flush()
        return changed[0]
