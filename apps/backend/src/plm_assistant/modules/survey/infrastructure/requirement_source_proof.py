"""Approved SurveyConclusion and exact terminal Review proof for Requirement."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.review.infrastructure.orm import (
    ReviewRow, ReviewRoundRow, ReviewSubjectSnapshotRow,
)
from plm_assistant.modules.survey.application.requirement_source_proof import (
    SurveyConclusionRequirementSourceProof,
)

from .orm import SurveyConclusionRow
from .survey_create_repository import _session


class SqlAlchemySurveyConclusionRequirementSourceProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_conclusion_id: uuid.UUID,
    ) -> SurveyConclusionRequirementSourceProof | None:
        if any(
            type(value) is not uuid.UUID or value.int == 0
            for value in (project_id, survey_conclusion_id)
        ):
            return None
        row = _session(transaction).execute(select(
            SurveyConclusionRow.survey_conclusion_id,
            SurveyConclusionRow.conclusion_series_id,
            SurveyConclusionRow.project_id,
            SurveyConclusionRow.survey_id,
            ReviewRow.review_id,
            ReviewRoundRow.review_round_id,
            SurveyConclusionRow.version_no,
            SurveyConclusionRow.content_fingerprint,
        ).join(
            ReviewRow,
            ReviewRow.review_id == SurveyConclusionRow.review_ref,
        ).join(
            ReviewRoundRow,
            (ReviewRoundRow.review_round_id
             == SurveyConclusionRow.review_round_ref)
            & (ReviewRoundRow.review_id == ReviewRow.review_id),
        ).join(
            ReviewSubjectSnapshotRow,
            (ReviewSubjectSnapshotRow.review_round_id
             == ReviewRoundRow.review_round_id)
            & (ReviewSubjectSnapshotRow.review_id == ReviewRow.review_id),
        ).where(
            SurveyConclusionRow.survey_conclusion_id == survey_conclusion_id,
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_state == "APPROVED",
            ReviewRow.scope == "PROJECT",
            ReviewRow.project_id == project_id,
            ReviewRow.subject_type == "SRV-05",
            ReviewRow.subject_id == SurveyConclusionRow.conclusion_series_id,
            ReviewRow.policy_code == "SURVEY_CONCLUSION_ALL_V1",
            ReviewRow.review_state == "APPROVED",
            ReviewRow.active_round_id.is_(None),
            ReviewRoundRow.scope == "PROJECT",
            ReviewRoundRow.project_id == project_id,
            ReviewRoundRow.subject_version_id == survey_conclusion_id,
            ReviewRoundRow.round_state == "APPROVED",
            ReviewSubjectSnapshotRow.scope == "PROJECT",
            ReviewSubjectSnapshotRow.project_id == project_id,
            ReviewSubjectSnapshotRow.subject_type == "SRV-05",
            ReviewSubjectSnapshotRow.subject_id
            == SurveyConclusionRow.conclusion_series_id,
            ReviewSubjectSnapshotRow.subject_version_id == survey_conclusion_id,
            ReviewSubjectSnapshotRow.content_fingerprint
            == SurveyConclusionRow.content_fingerprint,
            ReviewSubjectSnapshotRow.proof_schema_version == 1,
        ).with_for_update(
            read=True,
            of=(SurveyConclusionRow, ReviewRow, ReviewRoundRow,
                ReviewSubjectSnapshotRow),
        ).execution_options(populate_existing=True)).one_or_none()
        return (
            None if row is None
            else SurveyConclusionRequirementSourceProof(
                *row[:-1], bytes(row[-1]),
            )
        )
