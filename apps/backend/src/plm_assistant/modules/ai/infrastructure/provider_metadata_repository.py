"""Explicit safe Provider projection; never joins Secret ciphertext/version tables."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import select, tuple_

from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataEntry, AIProviderMetadataView
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
    AIProviderRow.created_at,
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

    def list_page(self, transaction: object, *, after: tuple[datetime, uuid.UUID] | None,
                  limit: int) -> list[AIProviderMetadataEntry]:
        if (type(limit) is not int or not 1 <= limit <= 201
                or (after is not None and (
                    type(after) is not tuple or len(after) != 2
                    or not isinstance(after[0], datetime) or after[0].tzinfo is None
                    or after[0].utcoffset() is None
                    or type(after[1]) is not uuid.UUID or after[1].int == 0))):
            raise ValueError("invalid Provider list page")
        statement = select(*_DETAIL_FIELDS).select_from(AIProviderRow).join(
            AIProviderConfigVersionRow,
            (AIProviderRow.current_config_version_ref
             == AIProviderConfigVersionRow.provider_config_version_id)
            & (AIProviderRow.ai_provider_id == AIProviderConfigVersionRow.ai_provider_id),
        )
        if after is not None:
            statement = statement.where(tuple_(
                AIProviderRow.created_at, AIProviderRow.ai_provider_id,
            ) < after)
        rows = _session(transaction).execute(statement.order_by(
            AIProviderRow.created_at.desc(), AIProviderRow.ai_provider_id.desc(),
        ).limit(limit).execution_options(autoflush=False)).all()
        return [AIProviderMetadataEntry(row.created_at, _view(row)) for row in rows]
