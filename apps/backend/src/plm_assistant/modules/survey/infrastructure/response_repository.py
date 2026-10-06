"""Caller-transaction Survey Response/Answer/Evidence append persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select

from plm_assistant.modules.project.infrastructure.orm import ProjectMemberRow
from plm_assistant.modules.survey.application.record_response import SurveyResponseRecordError
from plm_assistant.modules.survey.application.response_views import (
    FixedAnswerEvidence, SurveyResponseContext, SurveyResponseWriteView,
)

from .orm import (
    SurveyAnswerEvidenceRefRow, SurveyAnswerRow, SurveyAssignmentRow,
    SurveyQuestionOptionRow, SurveyQuestionRow, SurveyResponseRow, SurveyRoundRow,
)
from .survey_create_repository import _session


class SqlAlchemySurveyResponseRepository:
    def lock_context(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, survey_assignment_id: uuid.UUID,
        question_id: uuid.UUID, expected_lock_version: int,
        actor_id: uuid.UUID, actor_role: str, response_source: str,
    ) -> SurveyResponseContext:
        session = _session(transaction)
        round_row = session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        ).with_for_update(of=SurveyRoundRow)).scalar_one_or_none()
        if round_row is None:
            raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
        if round_row.round_state != "OPEN":
            raise SurveyResponseRecordError("SURVEY_ASSIGNMENT_STATE_INVALID")
        assignment = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_round_id == survey_round_id,
            SurveyAssignmentRow.survey_assignment_id == survey_assignment_id,
        ).with_for_update(of=SurveyAssignmentRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if assignment is None:
            raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
        if assignment.lock_version != expected_lock_version:
            raise SurveyResponseRecordError("CONFLICT_VERSION")
        if assignment.submission_state not in ("ASSIGNED", "IN_PROGRESS", "RETURNED"):
            raise SurveyResponseRecordError("SURVEY_ASSIGNMENT_STATE_INVALID")
        allowed = (response_source == "FACILITATED_RECORD"
                   and actor_role == "IMPLEMENTATION_MEMBER")
        if not allowed and assignment.assignee_user_id == actor_id:
            allowed = True
        if not allowed and assignment.assignee_user_id is None:
            allowed = session.execute(select(ProjectMemberRow.project_member_id).where(
                ProjectMemberRow.project_id == project_id,
                ProjectMemberRow.user_id == actor_id,
                ProjectMemberRow.department_id == assignment.department_id,
                ProjectMemberRow.state == "ACTIVE",
            ).with_for_update(read=True)).scalar_one_or_none() is not None
        if not allowed:
            raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
        question = session.execute(select(SurveyQuestionRow).where(
            SurveyQuestionRow.survey_version_id == assignment.survey_version_id,
            SurveyQuestionRow.question_id == question_id,
        ).with_for_update(read=True, of=SurveyQuestionRow)).scalar_one_or_none()
        if question is None:
            raise SurveyResponseRecordError("RESOURCE_NOT_FOUND")
        options = tuple(session.execute(select(
            SurveyQuestionOptionRow.option_code,
        ).where(
            SurveyQuestionOptionRow.question_row_id == question.question_row_id,
        ).order_by(SurveyQuestionOptionRow.ordinal)).scalars())
        return SurveyResponseContext(
            assignment.survey_assignment_id, assignment.survey_round_id,
            assignment.survey_id, assignment.survey_version_id,
            assignment.project_id, assignment.department_id,
            assignment.assignee_user_id, assignment.submission_state,
            assignment.lock_version, question.question_row_id,
            question.question_id, question.answer_type, options,
        )

    def append(
        self, transaction: object, *, context: SurveyResponseContext,
        survey_response_id: uuid.UUID, survey_answer_id: uuid.UUID,
        response_source: str, round_source_record_ref_id: uuid.UUID | None,
        correction_of_response_id: uuid.UUID | None, raw_answer: str | None,
        answer_value: object | None, evidence: tuple[FixedAnswerEvidence, ...],
        actor_id: uuid.UUID, recorded_at: datetime,
    ) -> SurveyResponseWriteView:
        session = _session(transaction)
        assignment = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.survey_assignment_id == context.survey_assignment_id,
            SurveyAssignmentRow.project_id == context.project_id,
        ).with_for_update(of=SurveyAssignmentRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if (assignment is None
                or assignment.lock_version != context.before_lock_version
                or assignment.submission_state != context.before_state):
            raise SurveyResponseRecordError("CONFLICT_VERSION")
        assignment.submission_state = "IN_PROGRESS"
        assignment.updated_by = actor_id
        assignment.updated_at = func.statement_timestamp()
        assignment.lock_version += 1
        response = SurveyResponseRow(
            survey_response_id=survey_response_id,
            survey_assignment_id=context.survey_assignment_id,
            survey_round_id=context.survey_round_id, survey_id=context.survey_id,
            survey_version_id=context.survey_version_id,
            project_id=context.project_id, question_row_id=context.question_row_id,
            response_source=response_source,
            round_source_record_ref_id=round_source_record_ref_id,
            correction_of_response_id=correction_of_response_id,
            recorded_by=actor_id, recorded_at=recorded_at,
        )
        answer = SurveyAnswerRow(
            survey_answer_id=survey_answer_id, survey_response_id=survey_response_id,
            survey_assignment_id=context.survey_assignment_id,
            question_row_id=context.question_row_id, project_id=context.project_id,
            raw_answer=raw_answer, answer_value=answer_value,
        )
        # Keep the write order explicit.  The response/answer cardinality check is
        # deferred until commit, while the answer has an immediate FK to response.
        session.add(response)
        session.flush()
        session.add(answer)
        session.flush()
        for ordinal, proof in enumerate(evidence):
            session.add(SurveyAnswerEvidenceRefRow(
                survey_answer_id=survey_answer_id,
                survey_response_id=survey_response_id,
                survey_assignment_id=context.survey_assignment_id,
                question_row_id=context.question_row_id,
                project_id=context.project_id, document_id=proof.document_id,
                document_version_id=proof.document_version_id,
                evidence_id=proof.evidence_id,
                observed_evidence_lock_version=proof.observed_evidence_lock_version,
                content_fingerprint=proof.content_fingerprint,
                recorded_by=proof.recorded_by, recorded_at=recorded_at,
                ordinal=ordinal,
            ))
        session.flush()
        session.refresh(assignment)
        session.refresh(response)
        return SurveyResponseWriteView(
            response.survey_response_id, answer.survey_answer_id,
            context.survey_assignment_id, context.survey_round_id,
            context.survey_version_id, context.project_id, context.question_id,
            response.response_source, response.round_source_record_ref_id,
            response.correction_of_response_id, response.recorded_by,
            response.recorded_at, assignment.submission_state,
            f'"v{assignment.lock_version}"', len(evidence),
        )

    def get_written(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_response_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyResponseWriteView | None:
        session = _session(transaction)
        response = session.execute(select(SurveyResponseRow).where(
            SurveyResponseRow.project_id == project_id,
            SurveyResponseRow.survey_response_id == survey_response_id,
            SurveyResponseRow.recorded_by == actor_id,
        )).scalar_one_or_none()
        if response is None:
            return None
        answer = session.execute(select(SurveyAnswerRow).where(
            SurveyAnswerRow.survey_response_id == survey_response_id,
        )).scalar_one_or_none()
        assignment = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.survey_assignment_id == response.survey_assignment_id,
        )).scalar_one_or_none()
        if answer is None or assignment is None:
            return None
        count = session.execute(select(func.count(
            SurveyAnswerEvidenceRefRow.survey_answer_evidence_ref_id)).where(
                SurveyAnswerEvidenceRefRow.survey_answer_id == answer.survey_answer_id,
            )).scalar_one()
        question_id = session.execute(select(SurveyQuestionRow.question_id).where(
            SurveyQuestionRow.question_row_id == response.question_row_id,
        )).scalar_one_or_none()
        if question_id is None:
            return None
        return SurveyResponseWriteView(
            response.survey_response_id, answer.survey_answer_id,
            response.survey_assignment_id, response.survey_round_id,
            response.survey_version_id, response.project_id, question_id,
            response.response_source, response.round_source_record_ref_id,
            response.correction_of_response_id, response.recorded_by,
            response.recorded_at, assignment.submission_state,
            f'"v{assignment.lock_version}"', count,
        )
