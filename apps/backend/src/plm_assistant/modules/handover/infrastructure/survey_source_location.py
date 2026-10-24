"""Handover-owned historical/public Survey source resolver."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow
from plm_assistant.modules.handover.application.survey_source_location import (
    HandoverSurveySourceLocation,
)

from .analysis_create_repository import _session
from .orm import (
    HandoverAnalysisItemRow, HandoverAnalysisRow, HandoverAnalysisVersionRow,
    HandoverItemEvidenceRefRow,
)


class SqlAlchemyHandoverSurveySourceLocation:
    def resolve(
        self, transaction: object, *, project_id: uuid.UUID,
        analysis_item_row_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
    ) -> HandoverSurveySourceLocation | None:
        values = (project_id, analysis_item_row_id, handover_analysis_version_id,
                  handover_analysis_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        session = _session(transaction)
        row = session.execute(select(
            HandoverAnalysisItemRow.analysis_item_id,
            HandoverAnalysisItemRow.item_state,
            HandoverAnalysisVersionRow.version_state,
            HandoverAnalysisRow.analysis_state,
            HandoverAnalysisRow.current_approved_version_ref,
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
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisRow.project_id == project_id,
        ).with_for_update(read=True)).one_or_none()
        if row is None:
            return None
        evidence = tuple(session.execute(select(
            HandoverItemEvidenceRefRow.evidence_id,
        ).join(
            EvidenceRow,
            EvidenceRow.evidence_id == HandoverItemEvidenceRefRow.evidence_id,
        ).where(
            HandoverItemEvidenceRefRow.analysis_item_row_id == analysis_item_row_id,
            HandoverItemEvidenceRefRow.handover_analysis_version_id
            == handover_analysis_version_id,
            HandoverItemEvidenceRefRow.handover_analysis_id == handover_analysis_id,
            HandoverItemEvidenceRefRow.project_id == project_id,
            EvidenceRow.scope == "PROJECT",
            EvidenceRow.project_id == project_id,
        ).order_by(HandoverItemEvidenceRefRow.ordinal)).scalars())
        declared = session.execute(select(
            HandoverItemEvidenceRefRow.evidence_id,
        ).where(
            HandoverItemEvidenceRefRow.analysis_item_row_id == analysis_item_row_id,
        )).scalars().all()
        if len(evidence) != len(declared):
            raise RuntimeError("Handover Survey source evidence scope mismatch")
        current = (
            row.version_state == "APPROVED"
            and row.analysis_state == "ACTIVE"
            and row.current_approved_version_ref == handover_analysis_version_id
            and row.item_state in ("CONFIRMED", "RESOLVED", "ACCEPTED_RISK")
        )
        return HandoverSurveySourceLocation(
            handover_analysis_id, handover_analysis_version_id,
            row.analysis_item_id, row.item_state, current, evidence,
        )

