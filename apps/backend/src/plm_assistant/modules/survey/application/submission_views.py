"""Locked Survey Assignment submission snapshot and immutable receipt."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SubmissionEvidenceSnapshot:
    evidence_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_lock_version: int
    content_fingerprint: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class CurrentSubmissionAnswer:
    survey_response_id: uuid.UUID
    survey_answer_id: uuid.UUID
    question_row_id: uuid.UUID
    answer_value: object
    response_source: str
    source_evidence_id: uuid.UUID | None
    evidence: tuple[SubmissionEvidenceSnapshot, ...]


@dataclass(frozen=True, slots=True)
class SubmissionQuestion:
    question_row_id: uuid.UUID
    question_id: uuid.UUID
    sequence_no: int
    answer_type: str
    validation_rule: dict
    required: bool
    condition_rule: dict | None
    evidence_required: bool
    option_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SurveyAssignmentSubmissionSnapshot:
    survey_assignment_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    department_id: uuid.UUID
    assignee_user_id: uuid.UUID | None
    before_lock_version: int
    questions: tuple[SubmissionQuestion, ...]
    answers: tuple[CurrentSubmissionAnswer, ...]


@dataclass(frozen=True, slots=True)
class SubmissionCompletenessReport:
    active_question_count: int
    answered_question_count: int
    evidence_count: int


@dataclass(frozen=True, slots=True)
class SurveyAssignmentSubmitReceipt:
    survey_assignment_id: uuid.UUID
    survey_round_id: uuid.UUID
    project_id: uuid.UUID
    submission_state: str
    etag: str
