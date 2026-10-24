"""PostgreSQL selection and locks for current Survey Workflow qualification."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.survey.application.workflow_qualification import (
    SurveyWorkflowQualificationLock,
)

from .conclusion_validation_repository import (
    SqlAlchemySurveyConclusionValidationRepository,
)
from .orm import SurveyConclusionRow, SurveyRow
from .survey_create_repository import _session


class SqlAlchemySurveyWorkflowQualificationRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemySurveyConclusionValidationRepository()

    def lock_only_current_approved(
        self, transaction: object, *, project_id: uuid.UUID,
    ) -> SurveyWorkflowQualificationLock | None:
        if (transaction is None or type(project_id) is not uuid.UUID
                or project_id.int == 0):
            return None
        session = _session(transaction)
        rows = session.execute(select(
            SurveyConclusionRow.survey_conclusion_id,
            SurveyConclusionRow.review_ref,
            SurveyConclusionRow.review_round_ref,
            SurveyRow.survey_state,
        ).join(
            SurveyRow,
            (SurveyRow.survey_id == SurveyConclusionRow.survey_id)
            & (SurveyRow.project_id == SurveyConclusionRow.project_id),
        ).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.conclusion_state == "APPROVED",
            SurveyRow.survey_state == "ACTIVE",
        ).order_by(
            SurveyConclusionRow.survey_conclusion_id,
        ).with_for_update(
            of=(SurveyConclusionRow, SurveyRow),
        ).execution_options(populate_existing=True)).all()
        if len(rows) != 1:
            return None
        conclusion_id, review_id, round_id, state = rows[0]
        if (type(review_id) is not uuid.UUID or review_id.int == 0
                or type(round_id) is not uuid.UUID or round_id.int == 0):
            return None
        snapshot = self._snapshots.lock_snapshot(
            transaction, project_id=project_id,
            survey_conclusion_id=conclusion_id,
        )
        if snapshot is None:
            return None
        return SurveyWorkflowQualificationLock(
            snapshot, state, review_id, round_id,
        )
