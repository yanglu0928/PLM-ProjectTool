"""AI-owned model first-write and Provider capability proof in one transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.domain.model_definition import AIModelDefinition, AIModelKind
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelCapabilityRow, AIModelRow
from plm_assistant.modules.ai.infrastructure.provider_orm import AIProviderConfigVersionRow, AIProviderRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active AI Model transaction is required")
    return session


class SqlAlchemyAIModelCreateRepository:
    def provider_accepts(self, transaction: object, *, definition: AIModelDefinition) -> bool:
        if type(definition) is not AIModelDefinition:
            return False
        row = _session(transaction).execute(
            select(AIProviderRow.provider_state, AIProviderConfigVersionRow.can_chat,
                   AIProviderConfigVersionRow.can_structured_output,
                   AIProviderConfigVersionRow.can_embedding, AIProviderConfigVersionRow.can_rerank)
            .select_from(AIProviderRow)
            .join(AIProviderConfigVersionRow,
                  (AIProviderRow.current_config_version_ref == AIProviderConfigVersionRow.provider_config_version_id)
                  & (AIProviderRow.ai_provider_id == AIProviderConfigVersionRow.ai_provider_id))
            .where(AIProviderRow.ai_provider_id == definition.provider_id)
            .with_for_update(of=AIProviderRow)
            .execution_options(autoflush=False)
        ).one_or_none()
        if row is None or row.provider_state == "RETIRED":
            return False
        return bool({AIModelKind.CHAT: row.can_chat, AIModelKind.EMBEDDING: row.can_embedding,
                     AIModelKind.RERANK: row.can_rerank}[definition.kind]
                    and (not definition.structured_output or row.can_structured_output))

    def create(self, transaction: object, *, definition: AIModelDefinition, actor_id: uuid.UUID) -> None:
        if (type(definition) is not AIModelDefinition or type(actor_id) is not uuid.UUID
                or actor_id.int == 0):
            raise ValueError("invalid AI Model first write")
        session = _session(transaction)
        session.execute(insert(AIModelRow).values(
            ai_model_id=definition.model_id, ai_provider_id=definition.provider_id,
            provider_model_key=definition.provider_model_key, model_kind=definition.kind.value,
            model_revision=definition.revision, embedding_dimension=definition.embedding_dimension,
            model_state="SUSPENDED", lock_version=0, created_by=actor_id,
        ))
        session.execute(insert(AIModelCapabilityRow).values(
            ai_model_id=definition.model_id, capability_code="STRUCTURED_OUTPUT",
            value_bool=definition.structured_output,
        ))
        if definition.context_window_tokens is not None:
            session.execute(insert(AIModelCapabilityRow).values(
                ai_model_id=definition.model_id, capability_code="CONTEXT_WINDOW_TOKENS",
                value_integer=definition.context_window_tokens,
            ))

    def belongs_to_provider(self, transaction: object, *, model_id: uuid.UUID,
                            provider_id: uuid.UUID) -> bool:
        if (type(model_id) is not uuid.UUID or model_id.int == 0
                or type(provider_id) is not uuid.UUID or provider_id.int == 0):
            return False
        return _session(transaction).execute(
            select(AIModelRow.ai_model_id).where(
                AIModelRow.ai_model_id == model_id, AIModelRow.ai_provider_id == provider_id,
            ).execution_options(autoflush=False)
        ).scalar_one_or_none() == model_id
