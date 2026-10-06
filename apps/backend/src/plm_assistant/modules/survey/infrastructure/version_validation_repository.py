"""Locked reconstruction of one immutable SurveyVersion aggregate."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import select

from plm_assistant.modules.survey.application.create_version import (
    SurveyOptionDraft, SurveyQuestionDraft, SurveySourceDraft,
)
from plm_assistant.modules.survey.application.validate_version import SurveyVersionSnapshot

from .orm import (
    SurveyQuestionOptionRow, SurveyQuestionRow, SurveyQuestionSourceRefRow,
    SurveyTargetDepartmentRow, SurveyVersionRow,
)
from .survey_create_repository import _session


class SqlAlchemySurveyVersionValidationRepository:
    def lock_snapshot(self, transaction: object, *, project_id: uuid.UUID,
                      survey_id: uuid.UUID,
                      survey_version_id: uuid.UUID) -> SurveyVersionSnapshot | None:
        values = (project_id, survey_id, survey_version_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        session = _session(transaction)
        version = session.execute(select(SurveyVersionRow).where(
            SurveyVersionRow.survey_version_id == survey_version_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.project_id == project_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if version is None:
            return None
        question_rows = session.execute(select(SurveyQuestionRow).where(
            SurveyQuestionRow.survey_version_id == survey_version_id,
        ).order_by(SurveyQuestionRow.sequence_no).with_for_update(read=True)
          .execution_options(populate_existing=True)).scalars().all()
        contiguous = [row.sequence_no for row in question_rows] == list(
            range(len(question_rows)))
        questions: list[SurveyQuestionDraft] = []
        for row in question_rows:
            option_rows = session.execute(select(SurveyQuestionOptionRow).where(
                SurveyQuestionOptionRow.question_row_id == row.question_row_id,
            ).order_by(SurveyQuestionOptionRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            source_rows = session.execute(select(SurveyQuestionSourceRefRow).where(
                SurveyQuestionSourceRefRow.question_row_id == row.question_row_id,
            ).order_by(SurveyQuestionSourceRefRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            contiguous = (contiguous
                          and [item.ordinal for item in option_rows]
                          == list(range(len(option_rows)))
                          and [item.ordinal for item in source_rows]
                          == list(range(len(source_rows))))
            questions.append(SurveyQuestionDraft(
                row.question_id, row.topic, row.question_text, row.objective,
                row.answer_type, copy.deepcopy(row.validation_rule), row.required,
                copy.deepcopy(row.condition_rule), row.expected_output,
                row.evidence_required,
                tuple(SurveyOptionDraft(
                    item.option_code, item.label, item.description,
                ) for item in option_rows),
                tuple(SurveySourceDraft(
                    item.source_kind, item.handover_item_row_id,
                    item.handover_analysis_version_id, item.handover_analysis_id,
                    item.capability_item_row_id, item.capability_baseline_version_id,
                    item.capability_baseline_id, item.template_document_version_id,
                    item.template_document_id, item.manual_source_note,
                ) for item in source_rows),
            ))
        target_rows = session.execute(select(SurveyTargetDepartmentRow).where(
            SurveyTargetDepartmentRow.survey_version_id == survey_version_id,
        ).order_by(SurveyTargetDepartmentRow.ordinal).with_for_update(read=True)
          .execution_options(populate_existing=True)).scalars().all()
        contiguous = (contiguous and [item.ordinal for item in target_rows]
                      == list(range(len(target_rows))))
        return SurveyVersionSnapshot(
            version.survey_id, version.survey_version_id, version.project_id,
            version.version_no, version.version_state,
            bytes(version.content_fingerprint), version.declared_question_count,
            version.declared_option_count, version.declared_source_count,
            version.declared_target_department_count, tuple(questions),
            tuple(item.department_id for item in target_rows), contiguous,
        )
