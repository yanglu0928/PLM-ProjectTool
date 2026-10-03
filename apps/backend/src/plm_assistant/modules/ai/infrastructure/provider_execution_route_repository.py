"""PostgreSQL projection of current post-Begin Provider execution facts."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AIProviderExecutionRouteMaterial,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow,
    AIProviderRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow,
    AIInvocationRow,
    AITaskRow,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
)


class SqlAlchemyAIProviderExecutionRouteRepository:
    def load_current(
        self, transaction: object, *, claim: AITaskExecutionClaim,
        ai_invocation_id: uuid.UUID,
    ) -> AIProviderExecutionRouteMaterial | None:
        if (type(claim) is not AITaskExecutionClaim
                or type(ai_invocation_id) is not uuid.UUID
                or not ai_invocation_id.int):
            return None
        claim.__post_init__()
        session = _session(transaction)
        row = session.execute(select(
            AITaskRow.ai_task_id,
            AIInvocationRow.ai_invocation_id,
            AITaskRow.project_id,
            AITaskRow.job_ref,
            AIInvocationRow.attempt_no,
            AIInvocationRow.egress_authorization_snapshot_id,
            AIEgressAuthorizationSnapshotRow.authorization_ref,
            AIInvocationRow.content_plan_ref,
            AIInvocationRow.request_payload_fingerprint,
            AIInvocationRow.ai_provider_id,
            AIInvocationRow.provider_config_version_id,
            AIInvocationRow.ai_model_id,
            AIProviderConfigVersionRow.provider_kind,
            AIProviderConfigVersionRow.endpoint_policy_ref,
            AIProviderConfigVersionRow.secret_ref,
            AIProviderConfigVersionRow.data_region,
            AIProviderConfigVersionRow.egress_class,
            AIModelRow.provider_model_key,
            AIModelRow.model_revision,
        ).join(
            AIInvocationRow,
            (AIInvocationRow.ai_task_id == AITaskRow.ai_task_id)
            & (AIInvocationRow.ai_invocation_id
               == AITaskRow.current_invocation_ref),
        ).join(
            AIEgressAuthorizationSnapshotRow,
            (AIEgressAuthorizationSnapshotRow.egress_authorization_snapshot_id
             == AIInvocationRow.egress_authorization_snapshot_id)
            & (AIEgressAuthorizationSnapshotRow.ai_task_id
               == AITaskRow.ai_task_id),
        ).join(
            AIProviderRow,
            AIProviderRow.ai_provider_id == AIInvocationRow.ai_provider_id,
        ).join(
            AIProviderConfigVersionRow,
            (AIProviderConfigVersionRow.provider_config_version_id
             == AIInvocationRow.provider_config_version_id)
            & (AIProviderConfigVersionRow.ai_provider_id
               == AIInvocationRow.ai_provider_id),
        ).join(
            AIModelRow,
            (AIModelRow.ai_model_id == AIInvocationRow.ai_model_id)
            & (AIModelRow.ai_provider_id == AIInvocationRow.ai_provider_id),
        ).where(
            AITaskRow.ai_task_id == claim.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == claim.project_id,
            AITaskRow.job_ref == claim.job_id,
            AITaskRow.requested_by == claim.actor_id,
            AITaskRow.trace_id == claim.trace_id,
            AITaskRow.input_fingerprint == claim.input_fingerprint,
            AITaskRow.task_state == "RUNNING",
            AITaskRow.current_invocation_ref == ai_invocation_id,
            AITaskRow.started_at.is_not(None),
            AITaskRow.completed_at.is_(None),
            AIInvocationRow.ai_invocation_id == ai_invocation_id,
            AIInvocationRow.attempt_no == claim.attempt_no,
            AIInvocationRow.scope == "PROJECT",
            AIInvocationRow.project_id == claim.project_id,
            AIInvocationRow.invocation_state == "PENDING",
            AIInvocationRow.started_at.is_(None),
            AIInvocationRow.completed_at.is_(None),
            AIInvocationRow.egress_authorization_mode == "AUTHORIZED",
            AIInvocationRow.egress_authorization_snapshot_id.is_not(None),
            AIInvocationRow.content_plan_ref == AITaskRow.content_plan_ref,
            AIEgressAuthorizationSnapshotRow.authorization_ref
            == claim.egress_authorization_ref,
            AIProviderRow.provider_state == "ACTIVE",
            AIProviderRow.current_config_version_ref
            == AIInvocationRow.provider_config_version_id,
            AIProviderConfigVersionRow.provider_kind == "OPENAI_COMPATIBLE",
            AIProviderConfigVersionRow.can_chat.is_(True),
            AIModelRow.model_kind == "CHAT",
            AIModelRow.model_state == "AVAILABLE",
        ).with_for_update(of=[
            AITaskRow, AIInvocationRow, AIProviderRow, AIModelRow,
        ]).execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None
        try:
            provider_kind = ProviderKind(row.provider_kind)
        except ValueError:
            return None
        return AIProviderExecutionRouteMaterial(
            row.ai_task_id,
            row.ai_invocation_id,
            row.project_id,
            row.job_ref,
            row.attempt_no,
            row.egress_authorization_snapshot_id,
            row.authorization_ref,
            row.content_plan_ref,
            bytes(row.request_payload_fingerprint),
            row.ai_provider_id,
            row.provider_config_version_id,
            row.ai_model_id,
            provider_kind,
            row.endpoint_policy_ref,
            row.secret_ref,
            row.data_region,
            row.egress_class,
            row.provider_model_key,
            row.model_revision,
        )
