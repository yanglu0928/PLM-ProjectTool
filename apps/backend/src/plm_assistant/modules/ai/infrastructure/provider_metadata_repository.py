"""Explicit safe Provider projection; never joins Secret ciphertext/version tables."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataView
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_create_repository import _session
from plm_assistant.modules.ai.infrastructure.provider_orm import AIProviderConfigVersionRow, AIProviderRow


_DETAIL_FIELDS = (
    AIProviderRow.ai_provider_id,
    AIProviderConfigVersionRow.provider_kind,
    AIProviderConfigVersionRow.display_name,
    AIProviderConfigVersionRow.endpoint_policy_ref,
    AIProviderConfigVersionRow.data_region,
    AIProviderConfigVersionRow.egress_class,
    AIProviderConfigVersionRow.secret_ref,
    AIProviderConfigVersionRow.can_chat,
    AIProviderConfigVersionRow.can_structured_output,
    AIProviderConfigVersionRow.can_embedding,
    AIProviderConfigVersionRow.can_rerank,
    AIProviderRow.provider_state,
    AIProviderConfigVersionRow.config_version_no,
    AIProviderRow.lock_version,
)


def _view(row: object) -> AIProviderMetadataView:
    capabilities = frozenset(item for enabled, item in (
        (row.can_chat, ProviderCapability.CHAT),
        (row.can_structured_output, ProviderCapability.STRUCTURED_OUTPUT),
        (row.can_embedding, ProviderCapability.EMBEDDING),
        (row.can_rerank, ProviderCapability.RERANK),
    ) if enabled)
    if (type(row.secret_ref) is not uuid.UUID or row.secret_ref.int == 0
            or type(row.lock_version) is not int or row.lock_version < 0
            or type(row.config_version_no) is not int or row.config_version_no < 1
            or not capabilities):
        raise RuntimeError("invalid AI Provider metadata")
    return AIProviderMetadataView(
        provider_id=row.ai_provider_id, kind=ProviderKind(row.provider_kind),
        display_name=row.display_name, endpoint_policy_ref=row.endpoint_policy_ref,
        data_region=row.data_region, egress_class=row.egress_class,
        capabilities=capabilities,
        secret_ref_masked="****" + row.secret_ref.hex[-8:],
        state=row.provider_state, config_version=row.config_version_no,
        lock_version=row.lock_version,
    )


class SqlAlchemyAIProviderMetadataRepository:
    def get(self, transaction: object, *, provider_id: uuid.UUID) -> AIProviderMetadataView | None:
        if type(provider_id) is not uuid.UUID or provider_id.int == 0:
            return None
        row = _session(transaction).execute(
            select(*_DETAIL_FIELDS).select_from(AIProviderRow).join(
                AIProviderConfigVersionRow,
                (AIProviderRow.current_config_version_ref
                 == AIProviderConfigVersionRow.provider_config_version_id)
                & (AIProviderRow.ai_provider_id == AIProviderConfigVersionRow.ai_provider_id),
            ).where(AIProviderRow.ai_provider_id == provider_id)
            .execution_options(autoflush=False)
        ).one_or_none()
        return _view(row) if row is not None else None
