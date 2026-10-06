"""Row-locked Survey metadata and archive persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.survey.application.change_survey import SurveyStateError
from plm_assistant.modules.survey.application.read_surveys import SurveyView

from .orm import SurveyRow, SurveyVersionRow
from .survey_create_repository import _session


def _view(row: SurveyRow) -> SurveyView:
    return SurveyView(
        row.survey_id, row.project_id, row.name, row.survey_state,
        row.current_approved_version_ref, row.created_by, row.created_at,
        row.updated_by, row.updated_at, f'"v{row.lock_version}"',
    )


class SqlAlchemySurveyStateRepository:
    def get(self, transaction: object, *, project_id: uuid.UUID,
            survey_id: uuid.UUID) -> SurveyView | None:
        row = _session(transaction).execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
        )).scalar_one_or_none()
        return None if row is None else _view(row)

    def patch(self, transaction: object, *, project_id: uuid.UUID,
              survey_id: uuid.UUID, expected_lock_version: int,
              name: str, actor_id: uuid.UUID) -> SurveyView:
        row = self._lock(transaction, project_id, survey_id)
        self._writable(row, expected_lock_version)
        self._review_fence(transaction, project_id, survey_id)
        if row.name == name:
            raise SurveyStateError("CONFLICT_STATE")
        row.name = name
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    def archive(self, transaction: object, *, project_id: uuid.UUID,
                survey_id: uuid.UUID, expected_lock_version: int,
                actor_id: uuid.UUID) -> SurveyView:
        row = self._lock(transaction, project_id, survey_id)
        self._writable(row, expected_lock_version)
        self._review_fence(transaction, project_id, survey_id)
        row.survey_state = "ARCHIVED"
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    @staticmethod
    def _lock(transaction: object, project_id: uuid.UUID,
              survey_id: uuid.UUID) -> SurveyRow:
        row = _session(transaction).execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
        ).with_for_update(of=SurveyRow)).scalar_one_or_none()
        if row is None:
            raise SurveyStateError("RESOURCE_NOT_FOUND")
        return row

    @staticmethod
    def _writable(row: SurveyRow, expected: int) -> None:
        if row.lock_version != expected:
            raise SurveyStateError("CONFLICT_VERSION")
        if row.survey_state != "ACTIVE":
            raise SurveyStateError("SURVEY_STATE_CONFLICT")

    @staticmethod
    def _review_fence(transaction: object, project_id: uuid.UUID,
                      survey_id: uuid.UUID) -> None:
        active = _session(transaction).execute(select(
            SurveyVersionRow.survey_version_id,
        ).where(
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.version_state == "IN_REVIEW",
        ).with_for_update(read=True).limit(1)).scalar_one_or_none()
        if active is not None:
            raise SurveyStateError("SURVEY_STATE_CONFLICT")

    @staticmethod
    def _advance(row: SurveyRow, actor_id: uuid.UUID) -> None:
        row.updated_by = actor_id
        row.updated_at = func.statement_timestamp()
        row.lock_version += 1

    @staticmethod
    def _refresh(transaction: object, row: SurveyRow) -> SurveyView:
        session = _session(transaction)
        session.flush()
        session.refresh(row)
        return _view(row)
