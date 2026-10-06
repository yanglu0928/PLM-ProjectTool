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
