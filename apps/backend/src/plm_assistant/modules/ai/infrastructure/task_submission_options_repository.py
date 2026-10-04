"""Current ACTIVE Provider and AVAILABLE structured CHAT route candidates."""

from __future__ import annotations

from sqlalchemy import select

from plm_assistant.modules.ai.application.task_submission_options import (
    AITaskRouteCandidate,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelCapabilityRow, AIModelRow
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow, AIProviderRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session


class SqlAlchemyAITaskSubmissionOptionsRepository:
    def list_routes(self, transaction: object, *, limit: int) -> tuple[AITaskRouteCandidate, ...]:
        if type(limit) is not int or not 1 <= limit <= 201:
            raise ValueError("invalid AI Task route limit")
        rows = _session(transaction).execute(select(
            AIProviderRow.ai_provider_id, AIProviderConfigVersionRow.display_name,
            AIProviderConfigVersionRow.data_region,
            AIProviderConfigVersionRow.provider_kind,
            AIProviderConfigVersionRow.endpoint_policy_ref,
            AIProviderConfigVersionRow.egress_class,
            AIModelRow.ai_model_id, AIModelRow.provider_model_key,
            AIModelRow.model_revision,
        ).join(
            AIProviderConfigVersionRow,
            (AIProviderConfigVersionRow.ai_provider_id == AIProviderRow.ai_provider_id)
            & (AIProviderConfigVersionRow.provider_config_version_id
               == AIProviderRow.current_config_version_ref),
        ).join(
            AIModelRow, AIModelRow.ai_provider_id == AIProviderRow.ai_provider_id,
        ).join(
            AIModelCapabilityRow,
            (AIModelCapabilityRow.ai_model_id == AIModelRow.ai_model_id)
            & (AIModelCapabilityRow.capability_code == "STRUCTURED_OUTPUT")
            & (AIModelCapabilityRow.value_bool.is_(True)),
        ).where(
            AIProviderRow.provider_state == "ACTIVE",
            AIProviderConfigVersionRow.can_chat.is_(True),
            AIProviderConfigVersionRow.can_structured_output.is_(True),
            AIModelRow.model_state == "AVAILABLE",
            AIModelRow.model_kind == "CHAT",
        ).order_by(
            AIProviderConfigVersionRow.display_name,
            AIModelRow.provider_model_key, AIModelRow.ai_model_id,
        ).limit(limit).execution_options(autoflush=False)).all()
        return tuple(AITaskRouteCandidate(
            row.ai_provider_id, row.ai_model_id, row.display_name, row.data_region,
            ProviderKind(row.provider_kind), row.endpoint_policy_ref,
            row.egress_class, row.provider_model_key, row.model_revision,
        ) for row in rows)
