"""Stable Round/target/Assignment lock set for completeness proof."""

from sqlalchemy import select

from plm_assistant.modules.survey.application.round_completeness import SurveyRoundCompletenessContext, SurveyRoundCompletenessError

from .orm import SurveyAssignmentRow, SurveyRoundRow, SurveyTargetDepartmentRow
from .survey_create_repository import _session


class SqlAlchemySurveyRoundCompletenessRepository:
    def lock_context(self, transaction, *, project_id, survey_round_id):
        session = _session(transaction)
        round_row = session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        ).with_for_update(of=SurveyRoundRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if round_row is None:
            raise SurveyRoundCompletenessError("RESOURCE_NOT_FOUND")
        if round_row.round_state != "OPEN":
            raise SurveyRoundCompletenessError()
        targets = tuple(session.execute(select(
            SurveyTargetDepartmentRow.department_id,
        ).where(
            SurveyTargetDepartmentRow.survey_version_id == round_row.survey_version_id,
        ).order_by(SurveyTargetDepartmentRow.ordinal).with_for_update(
            read=True, of=SurveyTargetDepartmentRow)).scalars())
        rows = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.survey_round_id == survey_round_id,
            SurveyAssignmentRow.project_id == project_id,
        ).order_by(SurveyAssignmentRow.survey_assignment_id).with_for_update(
            of=SurveyAssignmentRow).execution_options(populate_existing=True)).scalars().all()
        if any(row.submission_state != "VALIDATED" for row in rows):
            raise SurveyRoundCompletenessError()
        return SurveyRoundCompletenessContext(
            round_row.survey_round_id, round_row.survey_version_id,
            round_row.project_id, targets,
            tuple((row.survey_assignment_id, row.department_id, row.lock_version)
                  for row in rows))
