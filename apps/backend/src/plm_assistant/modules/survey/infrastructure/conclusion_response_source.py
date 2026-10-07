"""Survey-owned current VALIDATED chain-tail Response proof."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionResponseProof,
)

from .orm import (
    SurveyAnswerEvidenceRefRow, SurveyAnswerRow, SurveyAssignmentRow,
    SurveyResponseRow, SurveyRoundRow,
)
from .survey_create_repository import _session


class SqlAlchemyConclusionResponseProof:
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              survey_id: uuid.UUID, round_refs: tuple[uuid.UUID, ...],
              response_id: uuid.UUID) -> ConclusionResponseProof | None:
        if (transaction is None
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (project_id, survey_id, response_id))
                or type(round_refs) is not tuple or not round_refs
                or len(set(round_refs)) != len(round_refs)
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in round_refs)):
            return None
        session = _session(transaction)
        row = session.execute(select(
            SurveyResponseRow, SurveyAssignmentRow, SurveyRoundRow, SurveyAnswerRow,
        ).join(
            SurveyAssignmentRow,
            SurveyAssignmentRow.survey_assignment_id
            == SurveyResponseRow.survey_assignment_id,
        ).join(
            SurveyRoundRow,
            SurveyRoundRow.survey_round_id == SurveyResponseRow.survey_round_id,
        ).join(
            SurveyAnswerRow,
            SurveyAnswerRow.survey_response_id == SurveyResponseRow.survey_response_id,
        ).where(
            SurveyResponseRow.survey_response_id == response_id,
            SurveyResponseRow.project_id == project_id,
            SurveyResponseRow.survey_id == survey_id,
            SurveyResponseRow.survey_round_id.in_(round_refs),
            SurveyAssignmentRow.submission_state == "VALIDATED",
            SurveyRoundRow.round_state == "CLOSED",
            ~select(SurveyResponseRow.survey_response_id).where(
                SurveyResponseRow.correction_of_response_id == response_id,
            ).exists(),
        ).with_for_update(
            read=True,
            of=(SurveyResponseRow, SurveyAssignmentRow, SurveyRoundRow, SurveyAnswerRow),
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None:
            return None
        response, assignment, round_row, answer = row
        evidence = session.execute(select(
            SurveyAnswerEvidenceRefRow.evidence_id,
            SurveyAnswerEvidenceRefRow.document_id,
            SurveyAnswerEvidenceRefRow.document_version_id,
            SurveyAnswerEvidenceRefRow.observed_evidence_lock_version,
            SurveyAnswerEvidenceRefRow.content_fingerprint,
        ).where(
            SurveyAnswerEvidenceRefRow.survey_answer_id == answer.survey_answer_id,
            SurveyAnswerEvidenceRefRow.project_id == project_id,
        ).order_by(SurveyAnswerEvidenceRefRow.ordinal).with_for_update(
            read=True, of=SurveyAnswerEvidenceRefRow,
        )).all()
        fingerprint = canonical_payload_fingerprint({
            "response_id": str(response.survey_response_id),
            "answer_id": str(answer.survey_answer_id),
            "question_row_id": str(response.question_row_id),
            "response_source": response.response_source,
            "raw_answer": answer.raw_answer,
            "answer_value": answer.answer_value,
            "evidence": [{
                "evidence_id": str(item.evidence_id),
                "document_id": str(item.document_id),
                "document_version_id": str(item.document_version_id),
                "lock_version": item.observed_evidence_lock_version,
                "content_fingerprint": bytes(item.content_fingerprint).hex(),
            } for item in evidence],
        })
        return ConclusionResponseProof(
            response.survey_response_id, answer.survey_answer_id,
            response.survey_assignment_id, round_row.survey_round_id,
            response.survey_id, response.survey_version_id, response.project_id,
            assignment.department_id, response.question_row_id,
            response.response_source, fingerprint,
            tuple(item.evidence_id for item in evidence),
        )
