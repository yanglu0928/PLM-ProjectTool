"""Survey-owned append-only Round source persistence in caller transaction."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from plm_assistant.modules.survey.application.round_source import (
    SurveyRoundSourceAppend,
    SurveyRoundSourceError,
    SurveyRoundSourceRecord,
    VerifiedRoundProjectRecord,
)

from .orm import SurveyQuestionRow, SurveyRoundRow, SurveyRoundSourceRecordRow
from .survey_create_repository import _session


class SqlAlchemySurveyRoundSourceRepository:
    def append(
        self,
        transaction: object,
        command: SurveyRoundSourceAppend,
    ) -> SurveyRoundSourceRecord:
        if (type(command) is not SurveyRoundSourceAppend
                or type(command.survey_round_id) is not uuid.UUID
                or command.survey_round_id.int == 0
                or type(command.project_id) is not uuid.UUID
                or command.project_id.int == 0
                or command.question_id is not None and (
                    type(command.question_id) is not uuid.UUID
                    or command.question_id.int == 0
                )
                or type(command.verified_source) is not VerifiedRoundProjectRecord
                or type(command.recorded_at) is not datetime
                or command.recorded_at.tzinfo is None
                or command.recorded_at.utcoffset() is None):
            raise SurveyRoundSourceError("ROUND_SOURCE_INVALID")
        source = command.verified_source
        if (source.project_id != command.project_id
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    source.evidence_id, source.project_id, source.document_id,
                    source.document_version_id, source.recorded_by,
                ))
                or type(source.observed_evidence_lock_version) is not int
                or not 0 <= source.observed_evidence_lock_version < 2**63
                or type(source.content_fingerprint) is not bytes
                or len(source.content_fingerprint) != 32):
            raise SurveyRoundSourceError("RESOURCE_NOT_FOUND")

        session = _session(transaction)
        round_row = session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.survey_round_id == command.survey_round_id,
            SurveyRoundRow.project_id == command.project_id,
        ).with_for_update(of=SurveyRoundRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if round_row is None or round_row.round_state != "OPEN":
            raise SurveyRoundSourceError("RESOURCE_NOT_FOUND")

        question_row_id = None
        if command.question_id is not None:
            question_row_id = session.execute(select(
                SurveyQuestionRow.question_row_id,
            ).where(
                SurveyQuestionRow.project_id == round_row.project_id,
                SurveyQuestionRow.survey_id == round_row.survey_id,
                SurveyQuestionRow.survey_version_id == round_row.survey_version_id,
                SurveyQuestionRow.question_id == command.question_id,
            ).with_for_update(read=True, of=SurveyQuestionRow)).scalar_one_or_none()
            if question_row_id is None:
                raise SurveyRoundSourceError("RESOURCE_NOT_FOUND")

        ordinal = session.execute(select(
            func.coalesce(func.max(SurveyRoundSourceRecordRow.ordinal), -1) + 1,
        ).where(
            SurveyRoundSourceRecordRow.survey_round_id == round_row.survey_round_id,
        )).scalar_one()
        row = SurveyRoundSourceRecordRow(
            survey_round_id=round_row.survey_round_id,
            survey_id=round_row.survey_id,
            survey_version_id=round_row.survey_version_id,
            project_id=round_row.project_id,
            question_row_id=question_row_id,
            document_id=source.document_id,
            document_version_id=source.document_version_id,
            evidence_id=source.evidence_id,
            observed_evidence_lock_version=source.observed_evidence_lock_version,
            content_fingerprint=source.content_fingerprint,
            recorded_by=source.recorded_by,
            recorded_at=command.recorded_at.astimezone(timezone.utc),
            ordinal=ordinal,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return SurveyRoundSourceRecord(
            round_source_record_ref_id=row.round_source_record_ref_id,
            survey_round_id=row.survey_round_id,
            survey_id=row.survey_id,
            survey_version_id=row.survey_version_id,
            project_id=row.project_id,
            question_id=command.question_id,
            document_id=row.document_id,
            document_version_id=row.document_version_id,
            evidence_id=row.evidence_id,
            observed_evidence_lock_version=row.observed_evidence_lock_version,
            content_fingerprint=bytes(row.content_fingerprint),
            recorded_by=row.recorded_by,
            recorded_at=row.recorded_at,
            ordinal=row.ordinal,
            created_at=row.created_at,
        )
