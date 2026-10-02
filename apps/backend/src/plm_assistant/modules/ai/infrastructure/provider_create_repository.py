"""AI-owned first configuration write in the caller's single transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration,
)
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow, AIProviderRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active AI Provider transaction is required")
    return session


class SqlAlchemyAIProviderCreateRepository:
    def create(self, transaction: object, *, configuration: ProviderConfiguration,
               config_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        if (type(configuration) is not ProviderConfiguration
                or type(config_id) is not uuid.UUID or config_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or configuration.config_version != 1):
            raise ValueError("invalid AI Provider first configuration")
        session = _session(transaction)
        session.execute(insert(AIProviderRow).values(
            ai_provider_id=configuration.provider_id,
            current_config_version_ref=config_id,
            provider_state="CONFIGURED", lock_version=0, created_by=actor_id,
        ))
        session.execute(insert(AIProviderConfigVersionRow).values(
            provider_config_version_id=config_id,
            ai_provider_id=configuration.provider_id,
            config_version_no=configuration.config_version,
            provider_kind=configuration.kind.value,
            display_name=configuration.display_name,
            endpoint_policy_ref=configuration.endpoint_policy_ref,
            secret_ref=configuration.secret_ref,
            data_region=configuration.data_region,
            egress_class=configuration.egress_class,
            can_chat=ProviderCapability.CHAT in configuration.capabilities,
            can_structured_output=ProviderCapability.STRUCTURED_OUTPUT in configuration.capabilities,
            can_embedding=ProviderCapability.EMBEDDING in configuration.capabilities,
            can_rerank=ProviderCapability.RERANK in configuration.capabilities,
            created_by=actor_id,
        ))

    def initial_config_id(self, transaction: object, *, provider_id: uuid.UUID) -> uuid.UUID | None:
        if type(provider_id) is not uuid.UUID or provider_id.int == 0:
            return None
        return _session(transaction).execute(
            select(AIProviderConfigVersionRow.provider_config_version_id)
            .join(AIProviderRow, AIProviderConfigVersionRow.ai_provider_id == AIProviderRow.ai_provider_id)
            .where(AIProviderRow.ai_provider_id == provider_id,
                   AIProviderConfigVersionRow.config_version_no == 1)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()
