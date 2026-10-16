"""Survey Round creation and read persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from plm_assistant.modules.survey.application.create_round import (
    SurveyRoundCreateError,
)
from plm_assistant.modules.survey.application.round_views import (
    SurveyRoundSourceView,
    SurveyRoundView,
)

from .orm import (
    SurveyQuestionRow,
    SurveyRoundRow,
    SurveyRoundSourceRecordRow,
    SurveyRow,
    SurveyVersionRow,
)
from .survey_create_repository import _session


def _view(
    row: SurveyRoundRow, *, source_record_count: int = 0,
    source_records: tuple[SurveyRoundSourceView, ...] = (),
) -> SurveyRoundView:
    return SurveyRoundView(
        survey_round_id=row.survey_round_id,
        survey_id=row.survey_id,
        survey_version_id=row.survey_version_id,
        project_id=row.project_id,
        round_no=row.round_no,
        round_state=row.round_state,
        scheduled_start_at=row.scheduled_start_at,
        scheduled_end_at=row.scheduled_end_at,
        location_note=row.location_note,
        opened_by=row.opened_by,
        opened_at=row.opened_at,
        closed_by=row.closed_by,
        closed_at=row.closed_at,
        close_report_fingerprint=(
            None if row.close_report_fingerprint is None
            else bytes(row.close_report_fingerprint)
        ),
        cancelled_by=row.cancelled_by,
        cancelled_at=row.cancelled_at,
        cancellation_reason=row.cancellation_reason,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        etag=f'"v{row.lock_version}"',
        source_record_count=source_record_count,
        source_records=source_records,
    )


class SqlAlchemySurveyRoundRepository:
    def create(
        self, transaction: object, *, survey_round_id: uuid.UUID,
        project_id: uuid.UUID, survey_id: uuid.UUID,
        survey_version_id: uuid.UUID, scheduled_start_at: datetime | None,
        scheduled_end_at: datetime | None, location_note: str | None,
        actor_id: uuid.UUID,
    ) -> SurveyRoundView:
        session = _session(transaction)
        survey = session.execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
        ).with_for_update(of=SurveyRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if (survey is None or survey.survey_state != "ACTIVE"
                or survey.current_approved_version_ref != survey_version_id):
            raise SurveyRoundCreateError("SURVEY_VERSION_NOT_APPROVED")
        version = session.execute(select(SurveyVersionRow).where(
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.survey_version_id == survey_version_id,
            SurveyVersionRow.version_state == "APPROVED",
        ).with_for_update(read=True, of=SurveyVersionRow)).scalar_one_or_none()
        if version is None:
            raise SurveyRoundCreateError("SURVEY_VERSION_NOT_APPROVED")
        round_no = session.execute(select(
            func.coalesce(func.max(SurveyRoundRow.round_no), 0) + 1,
        ).where(SurveyRoundRow.survey_id == survey_id)).scalar_one()
        row = SurveyRoundRow(
            survey_round_id=survey_round_id,
            survey_id=survey_id,
            survey_version_id=survey_version_id,
            project_id=project_id,
            round_no=round_no,
            round_state="PLANNED",
            scheduled_start_at=scheduled_start_at,
            scheduled_end_at=scheduled_end_at,
            location_note=location_note,
            created_by=actor_id,
            updated_by=None,
            lock_version=0,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return _view(row)

    def get_initial(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyRoundView | None:
        row = _session(transaction).execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
            SurveyRoundRow.created_by == actor_id,
            SurveyRoundRow.round_state == "PLANNED",
            SurveyRoundRow.lock_version == 0,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        return None if row is None else _view(row)

    def list_rounds(
        self, transaction: object, *, project_id: uuid.UUID,
        after_created_at: datetime | None, after_round_id: uuid.UUID | None,
        limit: int,
    ) -> tuple[SurveyRoundView, ...]:
        source_count = select(func.count(
            SurveyRoundSourceRecordRow.round_source_record_ref_id,
        )).where(
            SurveyRoundSourceRecordRow.survey_round_id
            == SurveyRoundRow.survey_round_id,
        ).correlate(SurveyRoundRow).scalar_subquery()
        query = select(SurveyRoundRow, source_count).where(
            SurveyRoundRow.project_id == project_id,
        )
        if after_created_at is not None and after_round_id is not None:
            query = query.where(or_(
                SurveyRoundRow.created_at < after_created_at,
                and_(
                    SurveyRoundRow.created_at == after_created_at,
                    SurveyRoundRow.survey_round_id < after_round_id,
                ),
            ))
        rows = _session(transaction).execute(query.order_by(
            SurveyRoundRow.created_at.desc(),
            SurveyRoundRow.survey_round_id.desc(),
        ).limit(limit)).all()
        return tuple(_view(row, source_record_count=count) for row, count in rows)

    def get_round(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID,
    ) -> SurveyRoundView | None:
        session = _session(transaction)
        row = session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        records = session.execute(select(
            SurveyRoundSourceRecordRow,
            SurveyQuestionRow.question_id,
        ).outerjoin(
            SurveyQuestionRow,
            SurveyQuestionRow.question_row_id
            == SurveyRoundSourceRecordRow.question_row_id,
        ).where(
            SurveyRoundSourceRecordRow.project_id == project_id,
            SurveyRoundSourceRecordRow.survey_round_id == survey_round_id,
        ).order_by(SurveyRoundSourceRecordRow.ordinal)).all()
        sources = tuple(SurveyRoundSourceView(
            round_source_record_ref_id=source.round_source_record_ref_id,
            question_id=question_id,
            document_id=source.document_id,
            document_version_id=source.document_version_id,
            evidence_id=source.evidence_id,
            observed_evidence_lock_version=source.observed_evidence_lock_version,
            content_fingerprint=bytes(source.content_fingerprint),
            recorded_by=source.recorded_by,
            recorded_at=source.recorded_at,
            ordinal=source.ordinal,
        ) for source, question_id in records)
        return _view(row, source_record_count=len(sources), source_records=sources)
