"""Current approved Handover and exact terminal Review proof for Requirement."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.handover.application.requirement_source_proof import (
    HandoverRequirementSourceProof,
)
from plm_assistant.modules.review.infrastructure.orm import (
    ReviewRow, ReviewRoundRow, ReviewSubjectSnapshotRow,
)

from .analysis_create_repository import _session
from .orm import HandoverAnalysisRow, HandoverAnalysisVersionRow


class SqlAlchemyHandoverRequirementSourceProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
    ) -> HandoverRequirementSourceProof | None:
        if any(
            type(value) is not uuid.UUID or value.int == 0
            for value in (
                project_id, handover_analysis_id,
                handover_analysis_version_id,
            )
        ):
            return None
        row = _session(transaction).execute(select(
            HandoverAnalysisRow.handover_analysis_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id,
            HandoverAnalysisRow.project_id,
            ReviewRow.review_id,
            ReviewRoundRow.review_round_id,
            HandoverAnalysisVersionRow.version_no,
            HandoverAnalysisVersionRow.content_fingerprint,
        ).join(
            HandoverAnalysisVersionRow,
            (HandoverAnalysisVersionRow.handover_analysis_id
             == HandoverAnalysisRow.handover_analysis_id)
            & (HandoverAnalysisVersionRow.project_id
               == HandoverAnalysisRow.project_id),
        ).join(
            ReviewRow,
            ReviewRow.review_id == HandoverAnalysisVersionRow.review_ref,
        ).join(
            ReviewRoundRow,
            (ReviewRoundRow.review_round_id
             == HandoverAnalysisVersionRow.review_round_ref)
            & (ReviewRoundRow.review_id == ReviewRow.review_id),
        ).join(
            ReviewSubjectSnapshotRow,
            (ReviewSubjectSnapshotRow.review_round_id
             == ReviewRoundRow.review_round_id)
            & (ReviewSubjectSnapshotRow.review_id == ReviewRow.review_id),
        ).where(
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
            HandoverAnalysisRow.current_approved_version_ref
            == handover_analysis_version_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == handover_analysis_version_id,
            HandoverAnalysisVersionRow.version_state == "APPROVED",
            ReviewRow.scope == "PROJECT",
            ReviewRow.project_id == project_id,
            ReviewRow.subject_type == "HND-02",
            ReviewRow.subject_id == handover_analysis_id,
            ReviewRow.policy_code == "HANDOVER_ALL_V1",
            ReviewRow.review_state == "APPROVED",
            ReviewRow.active_round_id.is_(None),
            ReviewRoundRow.scope == "PROJECT",
            ReviewRoundRow.project_id == project_id,
            ReviewRoundRow.subject_version_id == handover_analysis_version_id,
            ReviewRoundRow.round_state == "APPROVED",
            ReviewSubjectSnapshotRow.scope == "PROJECT",
            ReviewSubjectSnapshotRow.project_id == project_id,
            ReviewSubjectSnapshotRow.subject_type == "HND-02",
            ReviewSubjectSnapshotRow.subject_id == handover_analysis_id,
            ReviewSubjectSnapshotRow.subject_version_id
            == handover_analysis_version_id,
            ReviewSubjectSnapshotRow.content_fingerprint
            == HandoverAnalysisVersionRow.content_fingerprint,
            ReviewSubjectSnapshotRow.proof_schema_version == 1,
        ).with_for_update(
            read=True,
            of=(HandoverAnalysisRow, HandoverAnalysisVersionRow, ReviewRow,
                ReviewRoundRow, ReviewSubjectSnapshotRow),
        ).execution_options(populate_existing=True)).one_or_none()
        return (
            None if row is None
            else HandoverRequirementSourceProof(*row[:-1], bytes(row[-1]))
        )
