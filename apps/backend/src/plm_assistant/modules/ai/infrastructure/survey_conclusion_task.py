"""SQL proof for completed Survey analysis suggestion provenance."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.application.survey_conclusion_task import (
    SurveyConclusionAITaskProof,
)

from .task_create_repository import _session
from .task_orm import AISuggestionPayloadRow, AITaskRow


class SqlAlchemySurveyConclusionAITaskProof:
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              ai_task_id: uuid.UUID) -> SurveyConclusionAITaskProof | None:
        if (transaction is None or any(
                type(value) is not uuid.UUID or value.int == 0
                for value in (project_id, ai_task_id))):
            return None
        row = _session(transaction).execute(select(
            AITaskRow.ai_task_id, AITaskRow.project_id,
            AITaskRow.current_invocation_ref,
            AISuggestionPayloadRow.suggestion_payload_id,
            AISuggestionPayloadRow.payload_fingerprint,
            AITaskRow.suggestion_state, AISuggestionPayloadRow.fact_status,
            AITaskRow.completed_at,
        ).join(
            AISuggestionPayloadRow,
            (AISuggestionPayloadRow.ai_task_id == AITaskRow.ai_task_id)
            & (AISuggestionPayloadRow.ai_invocation_id
               == AITaskRow.current_invocation_ref),
        ).where(
            AITaskRow.ai_task_id == ai_task_id,
            AITaskRow.scope == "PROJECT", AITaskRow.project_id == project_id,
            AITaskRow.task_type == "SURVEY_ANALYZE",
            AITaskRow.task_state == "SUCCEEDED",
            AITaskRow.suggestion_state.in_(("AVAILABLE", "ACCEPTED_TO_DRAFT")),
            AISuggestionPayloadRow.scope == "PROJECT",
            AISuggestionPayloadRow.project_id == project_id,
            AISuggestionPayloadRow.fact_status == "NOT_FORMAL_FACT",
        ).with_for_update(
            read=True, of=(AITaskRow, AISuggestionPayloadRow),
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None or type(row.payload_fingerprint) is not bytes \
                or len(row.payload_fingerprint) != 32:
            return None
        return SurveyConclusionAITaskProof(
            row.ai_task_id, row.project_id, row.current_invocation_ref,
            row.suggestion_payload_id, bytes(row.payload_fingerprint),
            row.suggestion_state, row.fact_status, row.completed_at,
        )
