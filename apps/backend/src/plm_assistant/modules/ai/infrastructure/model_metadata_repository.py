"""Bounded AIModel metadata projection; no Provider Secret or quality clearance."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, tuple_

from plm_assistant.modules.ai.application.model_metadata import AIModelMetadataView
from plm_assistant.modules.ai.domain.model_definition import AIModelDefinition, AIModelKind
from plm_assistant.modules.ai.infrastructure.model_create_repository import _session
from plm_assistant.modules.ai.infrastructure.model_orm import (
    AIModelCapabilityRow, AIModelRow, AIQualityProfileRefRow,
)


def _views(transaction: object, models: list[AIModelRow]) -> list[AIModelMetadataView]:
    if not models:
        return []
    session = _session(transaction)
    ids = [item.ai_model_id for item in models]
    capability_rows = session.execute(
        select(AIModelCapabilityRow.ai_model_id, AIModelCapabilityRow.capability_code,
               AIModelCapabilityRow.value_bool, AIModelCapabilityRow.value_integer)
        .where(AIModelCapabilityRow.ai_model_id.in_(ids))
        .execution_options(autoflush=False)
    ).all()
    quality_rows = session.execute(
        select(AIQualityProfileRefRow.ai_model_id, AIQualityProfileRefRow.quality_profile_ref)
        .where(AIQualityProfileRefRow.ai_model_id.in_(ids))
        .order_by(AIQualityProfileRefRow.ai_model_id, AIQualityProfileRefRow.quality_profile_ref)
        .execution_options(autoflush=False)
    ).all()
    capabilities: dict[uuid.UUID, dict[str, tuple[bool | None, int | None]]] = {ident: {} for ident in ids}
    qualities: dict[uuid.UUID, list[str]] = {ident: [] for ident in ids}
    for row in capability_rows:
        capabilities[row.ai_model_id][row.capability_code] = (row.value_bool, row.value_integer)
    for row in quality_rows:
        qualities[row.ai_model_id].append(row.quality_profile_ref)
    views = []
    for item in models:
        declared = capabilities[item.ai_model_id]
        structured = declared.get("STRUCTURED_OUTPUT")
        context = declared.get("CONTEXT_WINDOW_TOKENS")
        if (structured is None or type(structured[0]) is not bool or structured[1] is not None
                or context is not None and (context[0] is not None or type(context[1]) is not int)):
            raise RuntimeError("incomplete AI Model capability projection")
        definition = AIModelDefinition(
            model_id=item.ai_model_id, provider_id=item.ai_provider_id,
            provider_model_key=item.provider_model_key, kind=AIModelKind(item.model_kind),
            revision=item.model_revision, embedding_dimension=item.embedding_dimension,
            structured_output=structured[0],
            context_window_tokens=context[1] if context is not None else None,
        )
        if (item.model_state not in {"AVAILABLE", "SUSPENDED", "RETIRED"}
                or type(item.lock_version) is not int or item.lock_version < 0
                or not isinstance(item.created_at, datetime) or item.created_at.tzinfo is None):
            raise RuntimeError("invalid AI Model metadata")
        views.append(AIModelMetadataView(
            model_id=definition.model_id, provider_id=definition.provider_id,
            provider_model_key=definition.provider_model_key, kind=definition.kind,
            revision=definition.revision, embedding_dimension=definition.embedding_dimension,
            structured_output=definition.structured_output,
            context_window_tokens=definition.context_window_tokens,
            quality_profile_refs=tuple(qualities[item.ai_model_id]),
            state=item.model_state, lock_version=item.lock_version,
            created_at=item.created_at,
        ))
    return views


class SqlAlchemyAIModelMetadataRepository:
    def get(self, transaction: object, *, model_id: uuid.UUID) -> AIModelMetadataView | None:
        if type(model_id) is not uuid.UUID or model_id.int == 0:
            return None
        model = _session(transaction).execute(
            select(AIModelRow).where(AIModelRow.ai_model_id == model_id)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()
        return _views(transaction, [model])[0] if model is not None else None

    def list_page(self, transaction: object, *, after: tuple[datetime, uuid.UUID] | None,
                  limit: int) -> list[AIModelMetadataView]:
        if (type(limit) is not int or not 1 <= limit <= 201
                or after is not None and (
                    type(after) is not tuple or len(after) != 2
                    or not isinstance(after[0], datetime) or after[0].tzinfo is None
                    or after[0].utcoffset() is None
                    or type(after[1]) is not uuid.UUID or after[1].int == 0)):
            raise ValueError("invalid AI Model list page")
        statement = select(AIModelRow)
        if after is not None:
            statement = statement.where(tuple_(AIModelRow.created_at, AIModelRow.ai_model_id) < after)
        rows = _session(transaction).execute(statement.order_by(
            AIModelRow.created_at.desc(), AIModelRow.ai_model_id.desc(),
        ).limit(limit).execution_options(autoflush=False)).scalars().all()
        return _views(transaction, list(rows))
