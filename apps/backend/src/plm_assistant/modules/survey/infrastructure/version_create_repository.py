"""Survey-owned immutable definition aggregate persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, insert, select, text, update

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.survey.application.create_version import (
    CreatedSurveyVersion, SurveyLock, SurveyQuestionDraft, SurveyVersionCreateError,
)

from .orm import (
    SurveyQuestionOptionRow, SurveyQuestionRow, SurveyQuestionSourceRefRow,
    SurveyRow, SurveyTargetDepartmentRow, SurveyVersionRow,
)
from .survey_create_repository import _session


class SqlAlchemySurveyVersionCreateRepository:
    def lock_survey(self, transaction: object, *, project_id: uuid.UUID,
                    survey_id: uuid.UUID) -> SurveyLock | None:
        if any(type(value) is not uuid.UUID or value.int == 0
               for value in (project_id, survey_id)):
            return None
        session = _session(transaction)
        row = session.execute(select(SurveyRow).where(
            SurveyRow.survey_id == survey_id, SurveyRow.project_id == project_id,
        ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        latest = session.execute(select(
            SurveyVersionRow.survey_version_id, SurveyVersionRow.version_no,
        ).where(SurveyVersionRow.survey_id == survey_id,
                SurveyVersionRow.project_id == project_id)
          .order_by(SurveyVersionRow.version_no.desc()).limit(1)
          .execution_options(autoflush=False)).one_or_none()
        return SurveyLock(row.survey_id, row.project_id, row.survey_state,
                          row.current_approved_version_ref, row.lock_version,
                          0 if latest is None else latest.version_no,
                          None if latest is None else latest.survey_version_id)

    def create(self, transaction: object, *, survey: SurveyLock,
               survey_version_id: uuid.UUID,
               questions: tuple[SurveyQuestionDraft, ...],
               target_department_ids: tuple[uuid.UUID, ...],
               content_fingerprint: bytes, actor_id: uuid.UUID) -> CreatedSurveyVersion:
        if (type(survey) is not SurveyLock
                or type(survey_version_id) is not uuid.UUID or survey_version_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(content_fingerprint) is not bytes or len(content_fingerprint) != 32):
            raise SurveyVersionCreateError("VALIDATION_FAILED")
        session = _session(transaction)
        changed = session.execute(update(SurveyRow).where(
            SurveyRow.survey_id == survey.survey_id,
            SurveyRow.project_id == survey.project_id,
            SurveyRow.survey_state == "ACTIVE",
            SurveyRow.lock_version == survey.lock_version,
            ~exists(select(1).where(
                SurveyVersionRow.survey_id == survey.survey_id,
                SurveyVersionRow.version_state == "IN_REVIEW",
            )),
        ).values(updated_by=actor_id, updated_at=text("statement_timestamp()"),
                 lock_version=SurveyRow.lock_version + 1)
          .returning(SurveyRow.lock_version)).scalar_one_or_none()
        if changed != survey.lock_version + 1:
            raise SurveyVersionCreateError("CONFLICT_VERSION")
        option_count = sum(len(question.options) for question in questions)
        source_count = sum(len(question.sources) for question in questions)
        session.execute(insert(SurveyVersionRow).values(
            survey_version_id=survey_version_id, survey_id=survey.survey_id,
            project_id=survey.project_id, version_no=survey.highest_version_no + 1,
            version_state="DRAFT", content_fingerprint=content_fingerprint,
            declared_question_count=len(questions), declared_option_count=option_count,
            declared_source_count=source_count,
            declared_target_department_count=len(target_department_ids),
            supersedes_version_ref=survey.latest_version_id,
            review_ref=None, review_round_ref=None, created_by=actor_id,
        ))
        for sequence, question in enumerate(questions):
            row_id = uuid.UUID(new_uuid7())
            question_values = dict(
                question_row_id=row_id, survey_version_id=survey_version_id,
                survey_id=survey.survey_id, project_id=survey.project_id,
                question_id=question.question_id, sequence_no=sequence,
                topic=question.topic, question_text=question.question_text,
                objective=question.objective, answer_type=question.answer_type,
                validation_rule=question.validation_rule, required=question.required,
                expected_output=question.expected_output,
                evidence_required=question.evidence_required,
            )
            if question.condition_rule is not None:
                question_values["condition_rule"] = question.condition_rule
            session.execute(insert(SurveyQuestionRow).values(**question_values))
            for ordinal, option in enumerate(question.options):
                session.execute(insert(SurveyQuestionOptionRow).values(
                    question_option_id=uuid.UUID(new_uuid7()), question_row_id=row_id,
                    survey_version_id=survey_version_id, survey_id=survey.survey_id,
                    project_id=survey.project_id, option_code=option.option_code,
                    label=option.label, description=option.description, ordinal=ordinal,
                ))
            for ordinal, source in enumerate(question.sources):
                session.execute(insert(SurveyQuestionSourceRefRow).values(
                    question_source_ref_id=uuid.UUID(new_uuid7()), question_row_id=row_id,
                    survey_version_id=survey_version_id, survey_id=survey.survey_id,
                    project_id=survey.project_id, ordinal=ordinal,
                    **{name: getattr(source, name) for name in (
                        "source_kind", "handover_item_row_id",
                        "handover_analysis_version_id", "handover_analysis_id",
                        "capability_item_row_id", "capability_baseline_version_id",
                        "capability_baseline_id", "template_document_version_id",
                        "template_document_id", "manual_source_note",
                    )},
                ))
        for ordinal, department_id in enumerate(target_department_ids):
            session.execute(insert(SurveyTargetDepartmentRow).values(
                survey_target_department_ref_id=uuid.UUID(new_uuid7()),
                survey_version_id=survey_version_id, survey_id=survey.survey_id,
                project_id=survey.project_id, department_id=department_id,
                ordinal=ordinal,
            ))
        row = session.execute(select(SurveyVersionRow).where(
            SurveyVersionRow.survey_version_id == survey_version_id,
        )).scalar_one()
        return self._view(row, survey.lock_version)

    def initial_view(self, transaction: object, *, survey_version_id: uuid.UUID,
                     survey_id: uuid.UUID, project_id: uuid.UUID,
                     actor_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedSurveyVersion | None:
        values = (survey_version_id, survey_id, project_id, actor_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        row = _session(transaction).execute(select(SurveyVersionRow).where(
            SurveyVersionRow.survey_version_id == survey_version_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.created_by == actor_id,
            SurveyVersionRow.version_state == "DRAFT",
            SurveyVersionRow.review_ref.is_(None),
            SurveyVersionRow.review_round_ref.is_(None),
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        return None if row is None else self._view(row, expected_lock_version)

    @staticmethod
    def _view(row: SurveyVersionRow, expected: int) -> CreatedSurveyVersion:
        return CreatedSurveyVersion(
            row.survey_version_id, row.survey_id, row.project_id,
            row.version_no, row.version_state, bytes(row.content_fingerprint),
            row.supersedes_version_ref, row.created_by, row.created_at,
            expected, expected + 1,
        )
