"""AI-owned immutable Provider version append within the caller transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update

from plm_assistant.modules.ai.application.append_provider_config import CurrentAIProvider
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.ai.infrastructure.provider_create_repository import _session
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow, AIProviderRow,
)


class SqlAlchemyAIProviderAppendRepository:
    def lock_current(self, transaction: object, *, provider_id: uuid.UUID) -> CurrentAIProvider | None:
        if type(provider_id) is not uuid.UUID or provider_id.int == 0:
            return None
        session = _session(transaction)
        provider = session.execute(
            select(AIProviderRow)
            .where(AIProviderRow.ai_provider_id == provider_id)
            .with_for_update(of=AIProviderRow)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()
        if provider is None:
            return None
        version = session.execute(
            select(AIProviderConfigVersionRow.config_version_no,
                   AIProviderConfigVersionRow.provider_kind)
            .where(AIProviderConfigVersionRow.provider_config_version_id
                   == provider.current_config_version_ref,
                   AIProviderConfigVersionRow.ai_provider_id == provider_id)
            .execution_options(autoflush=False)
        ).one()
        return CurrentAIProvider(
            state=provider.provider_state, lock_version=provider.lock_version,
            config_version=version.config_version_no, kind=ProviderKind(version.provider_kind),
        )

    def version_belongs(self, transaction: object, *, provider_id: uuid.UUID,
                        config_id: uuid.UUID) -> bool:
        if (type(provider_id) is not uuid.UUID or provider_id.int == 0
                or type(config_id) is not uuid.UUID or config_id.int == 0):
            return False
        return _session(transaction).execute(
            select(AIProviderConfigVersionRow.provider_config_version_id)
            .where(AIProviderConfigVersionRow.provider_config_version_id == config_id,
                   AIProviderConfigVersionRow.ai_provider_id == provider_id)
            .execution_options(autoflush=False)
        ).scalar_one_or_none() is not None

    def version_number(self, transaction: object, *, provider_id: uuid.UUID,
                       config_id: uuid.UUID) -> int | None:
        if (type(provider_id) is not uuid.UUID or provider_id.int == 0
                or type(config_id) is not uuid.UUID or config_id.int == 0):
            return None
        return _session(transaction).execute(
            select(AIProviderConfigVersionRow.config_version_no)
            .where(AIProviderConfigVersionRow.provider_config_version_id == config_id,
                   AIProviderConfigVersionRow.ai_provider_id == provider_id)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()

    def current_configuration(self, transaction: object, *, provider_id: uuid.UUID) -> ProviderConfiguration | None:
        if type(provider_id) is not uuid.UUID or provider_id.int == 0:
            return None
        row = _session(transaction).execute(
            select(AIProviderConfigVersionRow).join(
                AIProviderRow,
                (AIProviderRow.ai_provider_id == AIProviderConfigVersionRow.ai_provider_id)
                & (AIProviderRow.current_config_version_ref
                   == AIProviderConfigVersionRow.provider_config_version_id),
            ).where(AIProviderRow.ai_provider_id == provider_id)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()
        if row is None:
            return None
        capabilities = frozenset(item for enabled, item in (
            (row.can_chat, ProviderCapability.CHAT),
            (row.can_structured_output, ProviderCapability.STRUCTURED_OUTPUT),
            (row.can_embedding, ProviderCapability.EMBEDDING),
            (row.can_rerank, ProviderCapability.RERANK),
        ) if enabled)
        return ProviderConfiguration(
            provider_id=provider_id, config_version=row.config_version_no,
            kind=ProviderKind(row.provider_kind), display_name=row.display_name,
            endpoint_policy_ref=row.endpoint_policy_ref, secret_ref=row.secret_ref,
            data_region=row.data_region, egress_class=row.egress_class,
            capabilities=capabilities,
        )

    def append(self, transaction: object, *, configuration: ProviderConfiguration,
               config_id: uuid.UUID, actor_id: uuid.UUID,
               expected_lock_version: int) -> None:
        if (type(configuration) is not ProviderConfiguration
                or configuration.config_version < 2
                or type(config_id) is not uuid.UUID or config_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(expected_lock_version) is not int or expected_lock_version < 0):
            raise ValueError("invalid AI Provider configuration append")
        session = _session(transaction)
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
        result = session.execute(
            update(AIProviderRow)
            .where(AIProviderRow.ai_provider_id == configuration.provider_id,
                   AIProviderRow.lock_version == expected_lock_version,
                   AIProviderRow.provider_state.in_(("CONFIGURED", "SUSPENDED")))
            .values(current_config_version_ref=config_id,
                    lock_version=AIProviderRow.lock_version + 1)
        )
        if result.rowcount != 1:
            raise RuntimeError("AI Provider version changed")
