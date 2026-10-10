"""Survey Assignment create and visibility-filtered read persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow,
    ProjectMemberRow,
)
from plm_assistant.modules.survey.application.assignment_views import (
    SurveyAnswerEvidenceView, SurveyAssignmentDetailView, SurveyAssignmentView,
    SurveyResponseReadView,
)
from plm_assistant.modules.survey.application.create_assignment import (
    SurveyAssignmentCreateError,
)

from .orm import (
    SurveyAnswerEvidenceRefRow, SurveyAnswerRow, SurveyAssignmentRow,
    SurveyQuestionRow, SurveyResponseRow,
    SurveyRoundRow,
    SurveyTargetDepartmentRow,
)
from .survey_create_repository import _session


def _view(row: SurveyAssignmentRow, response_count: int = 0) -> SurveyAssignmentView:
    return SurveyAssignmentView(
        row.survey_assignment_id, row.survey_round_id, row.survey_id,
        row.survey_version_id, row.project_id, row.department_id,
        row.assignee_user_id, row.submission_state, row.submitted_by,
        row.submitted_at, row.validated_by, row.validated_at, row.returned_by,
        row.returned_at, row.return_comment, row.created_by, row.created_at,
        row.updated_by, row.updated_at, f'"v{row.lock_version}"', response_count,
    )


class SqlAlchemySurveyAssignmentRepository:
    def create(
        self, transaction: object, *, survey_assignment_id: uuid.UUID,
        project_id: uuid.UUID, survey_round_id: uuid.UUID,
        department_id: uuid.UUID, assignee_user_id: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> SurveyAssignmentView:
        session = _session(transaction)
        round_row = session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_round_id == survey_round_id,
        ).with_for_update(read=True, of=SurveyRoundRow)).scalar_one_or_none()
        if round_row is None:
            raise SurveyAssignmentCreateError("RESOURCE_NOT_FOUND")
        if round_row.round_state != "OPEN":
            raise SurveyAssignmentCreateError("SURVEY_ASSIGNMENT_STATE_INVALID")
        target = session.execute(select(
            SurveyTargetDepartmentRow.survey_target_department_ref_id,
        ).join(
            DepartmentRow,
            and_(
                DepartmentRow.department_id
                == SurveyTargetDepartmentRow.department_id,
                DepartmentRow.project_id == SurveyTargetDepartmentRow.project_id,
            ),
        ).where(
            SurveyTargetDepartmentRow.survey_version_id
            == round_row.survey_version_id,
            SurveyTargetDepartmentRow.department_id == department_id,
            SurveyTargetDepartmentRow.project_id == project_id,
            DepartmentRow.state == "ACTIVE",
        ).with_for_update(read=True)).scalar_one_or_none()
        if target is None:
            raise SurveyAssignmentCreateError("RESOURCE_NOT_FOUND")
        if assignee_user_id is not None:
            member = session.execute(select(
                ProjectMemberRow.project_member_id,
            ).where(
                ProjectMemberRow.project_id == project_id,
                ProjectMemberRow.user_id == assignee_user_id,
                ProjectMemberRow.department_id == department_id,
                ProjectMemberRow.state == "ACTIVE",
            ).with_for_update(read=True)).scalar_one_or_none()
            if member is None:
                raise SurveyAssignmentCreateError("RESOURCE_NOT_FOUND")
        row = SurveyAssignmentRow(
            survey_assignment_id=survey_assignment_id,
            survey_round_id=survey_round_id, survey_id=round_row.survey_id,
            survey_version_id=round_row.survey_version_id,
            project_id=project_id, department_id=department_id,
            assignee_user_id=assignee_user_id, submission_state="ASSIGNED",
            created_by=actor_id, updated_by=None, lock_version=0,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return _view(row)

    def get_initial(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_assignment_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyAssignmentView | None:
        row = _session(transaction).execute(select(SurveyAssignmentRow).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_assignment_id == survey_assignment_id,
            SurveyAssignmentRow.created_by == actor_id,
            SurveyAssignmentRow.submission_state == "ASSIGNED",
            SurveyAssignmentRow.lock_version == 0,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        return None if row is None else _view(row)

    def list_assignments(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, actor_id: uuid.UUID, actor_role: str,
        after_created_at: datetime | None,
        after_assignment_id: uuid.UUID | None, limit: int,
    ) -> tuple[SurveyAssignmentView, ...]:
        count = select(func.count(SurveyResponseRow.survey_response_id)).where(
            SurveyResponseRow.survey_assignment_id
            == SurveyAssignmentRow.survey_assignment_id,
        ).correlate(SurveyAssignmentRow).scalar_subquery()
        query = select(SurveyAssignmentRow, count).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_round_id == survey_round_id,
        )
        query = self._visible(query, actor_id, actor_role, project_id)
        if after_created_at is not None and after_assignment_id is not None:
            query = query.where(or_(
                SurveyAssignmentRow.created_at < after_created_at,
                and_(SurveyAssignmentRow.created_at == after_created_at,
                     SurveyAssignmentRow.survey_assignment_id < after_assignment_id),
            ))
        rows = _session(transaction).execute(query.order_by(
            SurveyAssignmentRow.created_at.desc(),
            SurveyAssignmentRow.survey_assignment_id.desc(),
        ).limit(limit)).all()
        return tuple(_view(row, response_count) for row, response_count in rows)

    def get_assignment(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, survey_assignment_id: uuid.UUID,
        actor_id: uuid.UUID, actor_role: str,
    ) -> SurveyAssignmentView | None:
        count = select(func.count(SurveyResponseRow.survey_response_id)).where(
            SurveyResponseRow.survey_assignment_id
            == SurveyAssignmentRow.survey_assignment_id,
        ).correlate(SurveyAssignmentRow).scalar_subquery()
        query = select(SurveyAssignmentRow, count).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_round_id == survey_round_id,
            SurveyAssignmentRow.survey_assignment_id == survey_assignment_id,
        )
        row = _session(transaction).execute(self._visible(
            query, actor_id, actor_role, project_id,
        )).one_or_none()
        return None if row is None else _view(row[0], row[1])

    def get_assignment_detail(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, survey_assignment_id: uuid.UUID,
        actor_id: uuid.UUID, actor_role: str,
    ) -> SurveyAssignmentDetailView | None:
        session = _session(transaction)
        count = select(func.count(SurveyResponseRow.survey_response_id)).where(
            SurveyResponseRow.survey_assignment_id
            == SurveyAssignmentRow.survey_assignment_id,
        ).correlate(SurveyAssignmentRow).scalar_subquery()
        query = select(SurveyAssignmentRow, count).where(
            SurveyAssignmentRow.project_id == project_id,
            SurveyAssignmentRow.survey_round_id == survey_round_id,
            SurveyAssignmentRow.survey_assignment_id == survey_assignment_id,
        )
        row = session.execute(self._visible(
            query, actor_id, actor_role, project_id,
        )).one_or_none()
        if row is None:
            return None
        response_rows = session.execute(select(
            SurveyResponseRow, SurveyAnswerRow, SurveyQuestionRow.question_id,
        ).join(
            SurveyAnswerRow,
            SurveyAnswerRow.survey_response_id
            == SurveyResponseRow.survey_response_id,
        ).join(
            SurveyQuestionRow,
            SurveyQuestionRow.question_row_id == SurveyResponseRow.question_row_id,
        ).where(
            SurveyResponseRow.project_id == project_id,
            SurveyResponseRow.survey_assignment_id == survey_assignment_id,
        ).order_by(
            SurveyResponseRow.recorded_at,
            SurveyResponseRow.survey_response_id,
        )).all()
        answer_ids = tuple(answer.survey_answer_id for _, answer, _ in response_rows)
        evidence_by_answer: dict[uuid.UUID, list[SurveyAnswerEvidenceView]] = {
            identity: [] for identity in answer_ids
        }
        if answer_ids:
            evidence_rows = session.execute(select(
                SurveyAnswerEvidenceRefRow,
            ).where(
                SurveyAnswerEvidenceRefRow.survey_answer_id.in_(answer_ids),
            ).order_by(
                SurveyAnswerEvidenceRefRow.survey_answer_id,
                SurveyAnswerEvidenceRefRow.ordinal,
            )).scalars().all()
            for evidence in evidence_rows:
                evidence_by_answer[evidence.survey_answer_id].append(
                    SurveyAnswerEvidenceView(
                        evidence.evidence_id, evidence.document_id,
                        evidence.document_version_id,
                        evidence.observed_evidence_lock_version,
                        bytes(evidence.content_fingerprint), evidence.ordinal,
                    ))
        responses = tuple(SurveyResponseReadView(
            response.survey_response_id, question_id,
            response.response_source, response.round_source_record_ref_id,
            response.correction_of_response_id, response.recorded_by,
            response.recorded_at, answer.raw_answer, answer.answer_value,
            tuple(evidence_by_answer[answer.survey_answer_id]),
        ) for response, answer, question_id in response_rows)
        return SurveyAssignmentDetailView(_view(row[0], row[1]), responses)

    @staticmethod
    def _visible(query, actor_id: uuid.UUID, actor_role: str,
                 project_id: uuid.UUID):
        if actor_role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"):
            return query
        department = select(ProjectMemberRow.department_id).where(
            ProjectMemberRow.project_id == project_id,
            ProjectMemberRow.user_id == actor_id,
            ProjectMemberRow.state == "ACTIVE",
        ).scalar_subquery()
        return query.where(or_(
            SurveyAssignmentRow.assignee_user_id == actor_id,
            and_(SurveyAssignmentRow.assignee_user_id.is_(None),
                 SurveyAssignmentRow.department_id == department),
        ))
