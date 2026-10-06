"""Row-locked Survey Round schedule and lifecycle persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select

from plm_assistant.modules.survey.application.change_round import (
    SurveyRoundStateError,
)
from plm_assistant.modules.survey.application.round_views import SurveyRoundView

from .orm import SurveyRoundRow
from .round_repository import _view
from .survey_create_repository import _session


class SqlAlchemySurveyRoundStateRepository:
    def get(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID,
    ) -> SurveyRoundView | None:
        row = _session(transaction).execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        return None if row is None else _view(row)

    def patch(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        scheduled_start_at: datetime | None,
        scheduled_end_at: datetime | None, location_note: str | None,
        actor_id: uuid.UUID,
    ) -> SurveyRoundView:
        row = self._lock(transaction, project_id, survey_round_id)
        self._planned(row, expected_lock_version)
        if (row.scheduled_start_at == scheduled_start_at
                and row.scheduled_end_at == scheduled_end_at
                and row.location_note == location_note):
            raise SurveyRoundStateError("CONFLICT_STATE")
        row.scheduled_start_at = scheduled_start_at
        row.scheduled_end_at = scheduled_end_at
        row.location_note = location_note
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    def open(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        actor_id: uuid.UUID,
    ) -> SurveyRoundView:
        row = self._lock(transaction, project_id, survey_round_id)
        self._planned(row, expected_lock_version)
        occurred_at = func.statement_timestamp()
        row.round_state = "OPEN"
        row.opened_by = actor_id
        row.opened_at = occurred_at
        self._advance(row, actor_id, occurred_at=occurred_at)
        return self._refresh(transaction, row)

    def cancel(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        reason: str, actor_id: uuid.UUID,
    ) -> SurveyRoundView:
        row = self._lock(transaction, project_id, survey_round_id)
        self._planned(row, expected_lock_version)
        occurred_at = func.statement_timestamp()
        row.round_state = "CANCELLED"
        row.cancelled_by = actor_id
        row.cancelled_at = occurred_at
        row.cancellation_reason = reason
        self._advance(row, actor_id, occurred_at=occurred_at)
        return self._refresh(transaction, row)

    @staticmethod
    def _lock(
        transaction: object, project_id: uuid.UUID,
        survey_round_id: uuid.UUID,
    ) -> SurveyRoundRow:
        row = _session(transaction).execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        ).with_for_update(of=SurveyRoundRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if row is None:
            raise SurveyRoundStateError("RESOURCE_NOT_FOUND")
        return row

    @staticmethod
    def _planned(row: SurveyRoundRow, expected_lock_version: int) -> None:
        if row.lock_version != expected_lock_version:
            raise SurveyRoundStateError("CONFLICT_VERSION")
        if row.round_state != "PLANNED":
            raise SurveyRoundStateError("SURVEY_ROUND_STATE_CONFLICT")

    @staticmethod
    def _advance(
        row: SurveyRoundRow, actor_id: uuid.UUID, *,
        occurred_at: object | None = None,
    ) -> None:
        row.updated_by = actor_id
        row.updated_at = (
            occurred_at if occurred_at is not None else func.statement_timestamp()
        )
        row.lock_version += 1

    @staticmethod
    def _refresh(
        transaction: object, row: SurveyRoundRow,
    ) -> SurveyRoundView:
        session = _session(transaction)
        session.flush()
        session.refresh(row)
        return _view(row)
