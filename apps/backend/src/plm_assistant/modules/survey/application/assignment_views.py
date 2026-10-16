"""Stable internal Survey Assignment projections."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SurveyAssignmentView:
    survey_assignment_id: uuid.UUID
    survey_round_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    department_id: uuid.UUID
    assignee_user_id: uuid.UUID | None
    submission_state: str
    submitted_by: uuid.UUID | None
    submitted_at: datetime | None
    validated_by: uuid.UUID | None
    validated_at: datetime | None
    returned_by: uuid.UUID | None
    returned_at: datetime | None
    return_comment: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
    etag: str = '"v0"'
    response_count: int = 0


@dataclass(frozen=True, slots=True)
class SurveyAssignmentPage:
    items: tuple[SurveyAssignmentView, ...]
    next_created_at: datetime | None
    next_assignment_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class SurveyAnswerEvidenceView:
    evidence_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    ordinal: int = 0


@dataclass(frozen=True, slots=True)
class SurveyResponseReadView:
    survey_response_id: uuid.UUID
    question_id: uuid.UUID
    response_source: str
    round_source_record_ref_id: uuid.UUID | None
    correction_of_response_id: uuid.UUID | None
    recorded_by: uuid.UUID
    recorded_at: datetime
    raw_answer: str | None
    answer_value: object | None
    evidence: tuple[SurveyAnswerEvidenceView, ...] = ()


@dataclass(frozen=True, slots=True)
class SurveyAssignmentDetailView:
    assignment: SurveyAssignmentView
    responses: tuple[SurveyResponseReadView, ...] = ()
