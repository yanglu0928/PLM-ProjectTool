"""Internal Survey Response write projections and locked context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SurveyResponseContext:
    survey_assignment_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    department_id: uuid.UUID
    assignee_user_id: uuid.UUID | None
    before_state: str
    before_lock_version: int
    question_row_id: uuid.UUID
    question_id: uuid.UUID
    answer_type: str
    option_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FixedAnswerEvidence:
    evidence_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    recorded_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class SurveyResponseWriteView:
    survey_response_id: uuid.UUID
    survey_answer_id: uuid.UUID
    survey_assignment_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    question_id: uuid.UUID
    response_source: str
    round_source_record_ref_id: uuid.UUID | None
    correction_of_response_id: uuid.UUID | None
    recorded_by: uuid.UUID
    recorded_at: datetime
    assignment_state: str
    assignment_etag: str
    evidence_count: int
