"""Handover current-approved item proof for Survey writes."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.handover.application.survey_source_proof import (
    HandoverSurveySourceProof,
)

from .analysis_create_repository import _session
from .orm import HandoverAnalysisItemRow, HandoverAnalysisRow, HandoverAnalysisVersionRow


class SqlAlchemyHandoverSurveySourceProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_item_row_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
    ) -> HandoverSurveySourceProof | None:
        values = (project_id, analysis_item_row_id, handover_analysis_version_id,
                  handover_analysis_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        row = _session(transaction).execute(select(
            HandoverAnalysisItemRow.analysis_item_row_id,
            HandoverAnalysisItemRow.handover_analysis_version_id,
            HandoverAnalysisItemRow.handover_analysis_id,
            HandoverAnalysisItemRow.project_id,
            HandoverAnalysisItemRow.item_state,
        ).join(
            HandoverAnalysisVersionRow,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == HandoverAnalysisItemRow.handover_analysis_version_id,
        ).join(
            HandoverAnalysisRow,
            HandoverAnalysisRow.handover_analysis_id
            == HandoverAnalysisVersionRow.handover_analysis_id,
        ).where(
            HandoverAnalysisItemRow.analysis_item_row_id == analysis_item_row_id,
            HandoverAnalysisItemRow.handover_analysis_version_id
            == handover_analysis_version_id,
            HandoverAnalysisItemRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisItemRow.project_id == project_id,
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.version_state == "APPROVED",
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
            HandoverAnalysisRow.current_approved_version_ref
            == handover_analysis_version_id,
            HandoverAnalysisItemRow.item_state.in_((
                "CONFIRMED", "RESOLVED", "ACCEPTED_RISK",
            )),
        ).with_for_update(read=True)).one_or_none()
        return None if row is None else HandoverSurveySourceProof(*row)
