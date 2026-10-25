"""Survey-owned identity and immutable definition read projections."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.survey.application.read_surveys import (
    SurveyOptionView, SurveyQuestionView, SurveySourceView,
    SurveyTargetDepartmentView, SurveyVersionView, SurveyView,
)

from .orm import (
    SurveyQuestionOptionRow, SurveyQuestionRow, SurveyQuestionSourceRefRow,
    SurveyRow, SurveyTargetDepartmentRow, SurveyVersionRow,
)
from .survey_create_repository import _session


def _survey(row: SurveyRow) -> SurveyView:
    return SurveyView(
        survey_id=row.survey_id,
        project_id=row.project_id,
        name=row.name,
        survey_state=row.survey_state,
        current_approved_version_ref=row.current_approved_version_ref,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        etag=f'"v{row.lock_version}"',
    )


def _version(row: SurveyVersionRow, *,
             questions: tuple[SurveyQuestionView, ...] = (),
             targets: tuple[SurveyTargetDepartmentView, ...] = (),
             ) -> SurveyVersionView:
    return SurveyVersionView(
        survey_version_id=row.survey_version_id,
        survey_id=row.survey_id,
        project_id=row.project_id,
        version_no=row.version_no,
        version_state=row.version_state,
        content_fingerprint=bytes(row.content_fingerprint).hex(),
        declared_question_count=row.declared_question_count,
        declared_option_count=row.declared_option_count,
        declared_source_count=row.declared_source_count,
        declared_target_department_count=row.declared_target_department_count,
        supersedes_version_ref=row.supersedes_version_ref,
        review_ref=row.review_ref,
        review_round_ref=row.review_round_ref,
        created_by=row.created_by,
        created_at=row.created_at,
        questions=questions,
        target_departments=targets,
    )


class SqlAlchemySurveyReadRepository:
    def get_source(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID, survey_version_id: uuid.UUID,
        question_id: uuid.UUID, source_ordinal: int,
    ) -> SurveySourceView | None:
        row = _session(transaction).execute(select(
            SurveyQuestionSourceRefRow,
        ).join(
            SurveyQuestionRow,
            SurveyQuestionRow.question_row_id
            == SurveyQuestionSourceRefRow.question_row_id,
        ).join(
            SurveyVersionRow,
            SurveyVersionRow.survey_version_id
            == SurveyQuestionSourceRefRow.survey_version_id,
        ).where(
            SurveyQuestionSourceRefRow.project_id == project_id,
            SurveyQuestionSourceRefRow.survey_id == survey_id,
            SurveyQuestionSourceRefRow.survey_version_id == survey_version_id,
            SurveyQuestionSourceRefRow.ordinal == source_ordinal,
            SurveyQuestionRow.project_id == project_id,
            SurveyQuestionRow.survey_id == survey_id,
            SurveyQuestionRow.survey_version_id == survey_version_id,
            SurveyQuestionRow.question_id == question_id,
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.survey_id == survey_id,
        ).with_for_update(read=True)).scalar_one_or_none()
        return None if row is None else SurveySourceView(
            row.source_kind, row.handover_item_row_id,
            row.handover_analysis_version_id, row.handover_analysis_id,
            row.capability_item_row_id, row.capability_baseline_version_id,
            row.capability_baseline_id, row.template_document_version_id,
            row.template_document_id, row.manual_source_note, row.ordinal,
        )

    def list_surveys(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None, after_survey_id: uuid.UUID | None,
        limit: int,
    ) -> tuple[SurveyView, ...]:
        query = select(SurveyRow).where(SurveyRow.project_id == project_id)
        if after_updated_at is not None and after_survey_id is not None:
            query = query.where(or_(
                SurveyRow.updated_at < after_updated_at,
                and_(SurveyRow.updated_at == after_updated_at,
                     SurveyRow.survey_id < after_survey_id),
            ))
        rows = _session(transaction).execute(query.order_by(
            SurveyRow.updated_at.desc(), SurveyRow.survey_id.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_survey(row) for row in rows)

    def get_survey(self, transaction: object, *, project_id: uuid.UUID,
                   survey_id: uuid.UUID) -> SurveyView | None:
        row = _session(transaction).execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
        )).scalar_one_or_none()
        return None if row is None else _survey(row)

    def list_versions(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID, after_version_no: int | None, limit: int,
    ) -> tuple[SurveyVersionView, ...]:
        query = select(SurveyVersionRow).where(
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.survey_id == survey_id,
        )
        if after_version_no is not None:
            query = query.where(SurveyVersionRow.version_no < after_version_no)
        rows = _session(transaction).execute(query.order_by(
            SurveyVersionRow.version_no.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_version(row) for row in rows)

    def get_version(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_id: uuid.UUID, survey_version_id: uuid.UUID,
    ) -> SurveyVersionView | None:
        session = _session(transaction)
        version = session.execute(select(SurveyVersionRow).where(
            SurveyVersionRow.project_id == project_id,
            SurveyVersionRow.survey_id == survey_id,
            SurveyVersionRow.survey_version_id == survey_version_id,
        )).scalar_one_or_none()
        if version is None:
            return None

        question_rows = session.execute(select(SurveyQuestionRow).where(
            SurveyQuestionRow.project_id == project_id,
            SurveyQuestionRow.survey_id == survey_id,
            SurveyQuestionRow.survey_version_id == survey_version_id,
        ).order_by(SurveyQuestionRow.sequence_no)).scalars().all()
        question_row_ids = tuple(row.question_row_id for row in question_rows)

        options: dict[uuid.UUID, list[SurveyOptionView]] = defaultdict(list)
        sources: dict[uuid.UUID, list[SurveySourceView]] = defaultdict(list)
        if question_row_ids:
            for row in session.execute(select(SurveyQuestionOptionRow).where(
                SurveyQuestionOptionRow.project_id == project_id,
                SurveyQuestionOptionRow.survey_id == survey_id,
                SurveyQuestionOptionRow.survey_version_id == survey_version_id,
                SurveyQuestionOptionRow.question_row_id.in_(question_row_ids),
            ).order_by(
                SurveyQuestionOptionRow.question_row_id,
                SurveyQuestionOptionRow.ordinal,
            )).scalars():
                options[row.question_row_id].append(SurveyOptionView(
                    row.option_code, row.label, row.description, row.ordinal,
                ))
            for row in session.execute(select(SurveyQuestionSourceRefRow).where(
                SurveyQuestionSourceRefRow.project_id == project_id,
                SurveyQuestionSourceRefRow.survey_id == survey_id,
                SurveyQuestionSourceRefRow.survey_version_id == survey_version_id,
                SurveyQuestionSourceRefRow.question_row_id.in_(question_row_ids),
            ).order_by(
                SurveyQuestionSourceRefRow.question_row_id,
                SurveyQuestionSourceRefRow.ordinal,
            )).scalars():
                sources[row.question_row_id].append(SurveySourceView(
                    row.source_kind, row.handover_item_row_id,
                    row.handover_analysis_version_id, row.handover_analysis_id,
                    row.capability_item_row_id, row.capability_baseline_version_id,
                    row.capability_baseline_id, row.template_document_version_id,
                    row.template_document_id, row.manual_source_note, row.ordinal,
                ))

        questions = tuple(SurveyQuestionView(
            question_id=row.question_id,
            sequence_no=row.sequence_no,
            topic=row.topic,
            question_text=row.question_text,
            objective=row.objective,
            answer_type=row.answer_type,
            validation_rule=dict(row.validation_rule),
            required=row.required,
            condition_rule=(
                None if row.condition_rule is None else dict(row.condition_rule)
            ),
            expected_output=row.expected_output,
            evidence_required=row.evidence_required,
            options=tuple(options[row.question_row_id]),
            sources=tuple(sources[row.question_row_id]),
        ) for row in question_rows)
        targets = tuple(SurveyTargetDepartmentView(row.department_id, row.ordinal)
                        for row in session.execute(
                            select(SurveyTargetDepartmentRow).where(
                                SurveyTargetDepartmentRow.project_id == project_id,
                                SurveyTargetDepartmentRow.survey_id == survey_id,
                                SurveyTargetDepartmentRow.survey_version_id
                                == survey_version_id,
                            ).order_by(SurveyTargetDepartmentRow.ordinal),
                        ).scalars())
        return _version(version, questions=questions, targets=targets)
