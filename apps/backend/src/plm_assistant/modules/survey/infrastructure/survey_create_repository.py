"""Survey-owned initial identity persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.survey.application.create_survey import SurveyInitialView

from .orm import SurveyRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Survey transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Survey transaction is required")
    return session


class SqlAlchemySurveyCreateRepository:
    def create(
        self, transaction: object, *, survey_id: uuid.UUID,
        project_id: uuid.UUID, name: str, actor_id: uuid.UUID,
    ) -> None:
        if (type(survey_id) is not uuid.UUID or survey_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            raise ValueError("validated Survey identity required")
        _session(transaction).execute(insert(SurveyRow).values(
            survey_id=survey_id, project_id=project_id, name=name,
            survey_state="ACTIVE", current_approved_version_ref=None,
            created_by=actor_id, updated_by=None, lock_version=0,
        ))

    def initial_view(
        self, transaction: object, *, survey_id: uuid.UUID,
        project_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyInitialView | None:
        if (type(survey_id) is not uuid.UUID or survey_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            return None
        row = _session(transaction).execute(select(SurveyRow).where(
            SurveyRow.survey_id == survey_id,
            SurveyRow.project_id == project_id,
            SurveyRow.created_by == actor_id,
            SurveyRow.survey_state == "ACTIVE",
            SurveyRow.current_approved_version_ref.is_(None),
            SurveyRow.lock_version == 0,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        return SurveyInitialView(
            row.survey_id, row.project_id, row.name, row.created_at,
        )
