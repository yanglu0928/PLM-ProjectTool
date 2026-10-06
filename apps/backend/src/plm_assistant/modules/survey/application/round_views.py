"""Stable internal Survey Round read projections."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SurveyRoundSourceView:
    round_source_record_ref_id: uuid.UUID
    question_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    evidence_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: bytes = field(repr=False)
    recorded_by: uuid.UUID
    recorded_at: datetime
    ordinal: int


@dataclass(frozen=True, slots=True)
class SurveyRoundView:
    survey_round_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    project_id: uuid.UUID
    round_no: int
    round_state: str
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    location_note: str | None
    opened_by: uuid.UUID | None
    opened_at: datetime | None
    closed_by: uuid.UUID | None
    closed_at: datetime | None
    close_report_fingerprint: bytes | None = field(repr=False)
    cancelled_by: uuid.UUID | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_by: uuid.UUID | None = None
    updated_at: datetime | None = None
    etag: str = '"v0"'
    source_record_count: int = 0
    source_records: tuple[SurveyRoundSourceView, ...] = ()


@dataclass(frozen=True, slots=True)
class SurveyRoundPage:
    items: tuple[SurveyRoundView, ...]
    next_created_at: datetime | None
    next_round_id: uuid.UUID | None
    has_more: bool
