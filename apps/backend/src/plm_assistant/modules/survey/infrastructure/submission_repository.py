"""Survey Assignment current-answer snapshot and SUBMITTED transition."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.orm import aliased

from plm_assistant.modules.project.infrastructure.orm import ProjectMemberRow
from plm_assistant.modules.survey.application.submission_views import (
    CurrentSubmissionAnswer, SubmissionEvidenceSnapshot, SubmissionQuestion,
    SurveyAssignmentSubmissionSnapshot, SurveyAssignmentSubmitReceipt,
)

from .orm import (
    SurveyAnswerEvidenceRefRow, SurveyAnswerRow, SurveyAssignmentRow,
    SurveyQuestionOptionRow, SurveyQuestionRow, SurveyResponseRow, SurveyRoundRow,
    SurveyRoundSourceRecordRow,
)
from .survey_create_repository import _session


class SqlAlchemySurveyAssignmentSubmissionRepository:
    @staticmethod
    def _allowed(session, assignment, actor_id, actor_role):
        if actor_role == "IMPLEMENTATION_MEMBER" or assignment.assignee_user_id == actor_id:
            return True
        if assignment.assignee_user_id is not None:
            return False
        return session.execute(select(ProjectMemberRow.project_member_id).where(
            ProjectMemberRow.project_id == assignment.project_id,
            ProjectMemberRow.user_id == actor_id,
            ProjectMemberRow.department_id == assignment.department_id,
            ProjectMemberRow.state == "ACTIVE",
        ).with_for_update(read=True)).scalar_one_or_none() is not None

    def lock_snapshot(
        self, transaction, *, project_id, survey_round_id, survey_assignment_id,
        expected_lock_version, actor_id, actor_role,
    ) -> SurveyAssignmentSubmissionSnapshot:
        session = _session(transaction)
        round_row = session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        ).with_for_update(of=SurveyRoundRow)).scalar_one_or_none()
        assignment = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_round_id == survey_round_id,
            SurveyAssignmentRow.survey_assignment_id == survey_assignment_id,
        ).with_for_update(of=SurveyAssignmentRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if round_row is None or assignment is None:
            return None
        if round_row.round_state != "OPEN" or assignment.submission_state != "IN_PROGRESS":
            raise ValueError("SURVEY_ASSIGNMENT_STATE_INVALID")
        if assignment.lock_version != expected_lock_version:
            raise ValueError("CONFLICT_VERSION")
        if not self._allowed(session, assignment, actor_id, actor_role):
            raise LookupError("RESOURCE_NOT_FOUND")

        question_rows = session.execute(select(SurveyQuestionRow).where(
            SurveyQuestionRow.survey_version_id == assignment.survey_version_id,
        ).order_by(SurveyQuestionRow.sequence_no).with_for_update(
            read=True, of=SurveyQuestionRow)).scalars().all()
        options: dict[uuid.UUID, list[str]] = {}
        if question_rows:
            for row_id, code in session.execute(select(
                    SurveyQuestionOptionRow.question_row_id,
                    SurveyQuestionOptionRow.option_code,
            ).where(SurveyQuestionOptionRow.question_row_id.in_([
                item.question_row_id for item in question_rows
            ])).order_by(
                SurveyQuestionOptionRow.question_row_id,
                SurveyQuestionOptionRow.ordinal,
            )):
                options.setdefault(row_id, []).append(code)
        questions = tuple(SubmissionQuestion(
            row.question_row_id, row.question_id, row.sequence_no, row.answer_type,
            copy.deepcopy(row.validation_rule), row.required,
            copy.deepcopy(row.condition_rule), row.evidence_required,
            tuple(options.get(row.question_row_id, ())),
        ) for row in question_rows)

        successor = aliased(SurveyResponseRow)
        pairs = session.execute(select(SurveyResponseRow, SurveyAnswerRow).join(
            SurveyAnswerRow,
            SurveyAnswerRow.survey_response_id == SurveyResponseRow.survey_response_id,
        ).where(
            SurveyResponseRow.survey_assignment_id == survey_assignment_id,
            ~exists(select(1).where(
                successor.correction_of_response_id
                == SurveyResponseRow.survey_response_id)),
        ).with_for_update(read=True, of=(SurveyResponseRow, SurveyAnswerRow))).all()
        answer_ids = [answer.survey_answer_id for _, answer in pairs]
        evidence: dict[uuid.UUID, list[SubmissionEvidenceSnapshot]] = {}
        if answer_ids:
            rows = session.execute(select(SurveyAnswerEvidenceRefRow).where(
                SurveyAnswerEvidenceRefRow.survey_answer_id.in_(answer_ids),
            ).order_by(
                SurveyAnswerEvidenceRefRow.survey_answer_id,
                SurveyAnswerEvidenceRefRow.ordinal,
            ).with_for_update(read=True, of=SurveyAnswerEvidenceRefRow)).scalars().all()
            for row in rows:
                evidence.setdefault(row.survey_answer_id, []).append(
                    SubmissionEvidenceSnapshot(
                        row.evidence_id, row.document_id, row.document_version_id,
                        row.observed_evidence_lock_version,
                        bytes(row.content_fingerprint)))
        source_refs = {response.round_source_record_ref_id for response, _ in pairs
                       if response.round_source_record_ref_id is not None}
        source_evidence = {}
        if source_refs:
            source_evidence = dict(session.execute(select(
                SurveyRoundSourceRecordRow.round_source_record_ref_id,
                SurveyRoundSourceRecordRow.evidence_id,
            ).where(
                SurveyRoundSourceRecordRow.round_source_record_ref_id.in_(source_refs)
            ).with_for_update(read=True, of=SurveyRoundSourceRecordRow)).all())
        answers = tuple(CurrentSubmissionAnswer(
            response.survey_response_id, answer.survey_answer_id,
            response.question_row_id, copy.deepcopy(answer.answer_value),
            response.response_source,
            source_evidence.get(response.round_source_record_ref_id),
            tuple(evidence.get(answer.survey_answer_id, ())),
        ) for response, answer in pairs)
        return SurveyAssignmentSubmissionSnapshot(
            assignment.survey_assignment_id, assignment.survey_round_id,
            assignment.survey_version_id, assignment.project_id,
            assignment.department_id, assignment.assignee_user_id,
            assignment.lock_version, questions, answers)

    def submit(self, transaction, *, snapshot, actor_id):
        session = _session(transaction)
        assignment = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.survey_assignment_id == snapshot.survey_assignment_id,
            SurveyAssignmentRow.project_id == snapshot.project_id,
        ).with_for_update(of=SurveyAssignmentRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if (assignment is None or assignment.submission_state != "IN_PROGRESS"
                or assignment.lock_version != snapshot.before_lock_version):
            raise ValueError("CONFLICT_VERSION")
        assignment.submission_state = "SUBMITTED"
        assignment.submitted_by = actor_id
        assignment.submitted_at = func.statement_timestamp()
        assignment.updated_by = actor_id
        assignment.updated_at = func.statement_timestamp()
        assignment.lock_version += 1
        session.flush(); session.refresh(assignment)
        return SurveyAssignmentSubmitReceipt(
            assignment.survey_assignment_id, assignment.survey_round_id,
            assignment.project_id, "SUBMITTED", f'"v{assignment.lock_version}"')

    def replay(self, transaction, *, project_id, survey_round_id,
               survey_assignment_id, actor_id, actor_role, result_version):
        session = _session(transaction)
        assignment = session.execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_round_id == survey_round_id,
            SurveyAssignmentRow.survey_assignment_id == survey_assignment_id,
        ).with_for_update(read=True, of=SurveyAssignmentRow)).scalar_one_or_none()
        if (assignment is None
                or not self._allowed(session, assignment, actor_id, actor_role)):
            return None
        return SurveyAssignmentSubmitReceipt(
            assignment.survey_assignment_id, assignment.survey_round_id,
            assignment.project_id, "SUBMITTED", f'"v{result_version}"')
