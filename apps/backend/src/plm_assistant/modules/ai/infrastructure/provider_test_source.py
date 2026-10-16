"""Locked current Provider/config snapshot for an authorized Test submission."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.ai.application.submit_provider_test import CurrentProviderTestSource
from plm_assistant.modules.ai.infrastructure.provider_create_repository import _session
from plm_assistant.modules.ai.infrastructure.provider_orm import AIProviderConfigVersionRow, AIProviderRow


class SqlAlchemyAIProviderTestSource:
    def lock_current(self, transaction: object, *, provider_id: uuid.UUID) -> CurrentProviderTestSource | None:
        if type(provider_id) is not uuid.UUID or not provider_id.int:
            return None
        session = _session(transaction)
        provider = session.execute(select(AIProviderRow).where(
            AIProviderRow.ai_provider_id == provider_id,
        ).with_for_update(of=AIProviderRow).execution_options(autoflush=False)).scalar_one_or_none()
        if provider is None:
            return None
        row = session.execute(select(AIProviderConfigVersionRow).where(
            AIProviderConfigVersionRow.provider_config_version_id == provider.current_config_version_ref,
            AIProviderConfigVersionRow.ai_provider_id == provider_id,
        ).execution_options(autoflush=False)).scalar_one()
        capabilities = frozenset(item for enabled, item in (
            (row.can_chat, ProviderCapability.CHAT),
            (row.can_structured_output, ProviderCapability.STRUCTURED_OUTPUT),
            (row.can_embedding, ProviderCapability.EMBEDDING),
            (row.can_rerank, ProviderCapability.RERANK),
        ) if enabled)
        config = ProviderConfiguration(
            provider_id=provider_id, config_version=row.config_version_no,
            kind=ProviderKind(row.provider_kind), display_name=row.display_name,
            endpoint_policy_ref=row.endpoint_policy_ref, secret_ref=row.secret_ref,
            data_region=row.data_region, egress_class=row.egress_class,
            capabilities=capabilities,
        )
        return CurrentProviderTestSource(row.provider_config_version_id,
                                         provider.lock_version, provider.provider_state, config)
