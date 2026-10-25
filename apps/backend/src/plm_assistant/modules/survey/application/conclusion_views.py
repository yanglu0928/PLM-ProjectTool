"""Stable internal projections for immutable SurveyConclusion versions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DepartmentConclusionView:
    department_conclusion_id: uuid.UUID
    department_id: uuid.UUID
    title: str
    statement: str
    response_refs: tuple[uuid.UUID, ...]
    ordinal: int


@dataclass(frozen=True, slots=True)
class ModuleConclusionView:
    module_conclusion_id: uuid.UUID
    module_key: str
    title: str
    statement: str
    response_refs: tuple[uuid.UUID, ...]
    ordinal: int


@dataclass(frozen=True, slots=True)
class ConclusionEvidenceView:
    conclusion_evidence_ref_id: uuid.UUID
    reference_role: str
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    evidence_id: uuid.UUID
    observed_evidence_lock_version: int
    content_fingerprint: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class ConclusionOpenIssueView:
    conclusion_open_issue_ref_id: uuid.UUID
    issue_owner_module: str
    issue_object_type: str
    issue_id: uuid.UUID
    observed_issue_state: str
    observed_lock_version: int
    is_blocking: bool
    ordinal: int


@dataclass(frozen=True, slots=True)
class SurveyConclusionSummaryView:
    survey_conclusion_id: uuid.UUID
    conclusion_series_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    round_refs: tuple[uuid.UUID, ...]
    ai_task_refs: tuple[uuid.UUID, ...]
    version_no: int
    conclusion_state: str
    content_fingerprint: str
    declared_department_count: int
    declared_module_count: int
    declared_evidence_count: int
    declared_open_issue_count: int
    supersedes_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SurveyConclusionView:
    summary: SurveyConclusionSummaryView
    department_conclusions: tuple[DepartmentConclusionView, ...]
    module_conclusions: tuple[ModuleConclusionView, ...]
    evidence_refs: tuple[ConclusionEvidenceView, ...]
    open_issue_refs: tuple[ConclusionOpenIssueView, ...]


@dataclass(frozen=True, slots=True)
class SurveyConclusionPage:
    items: tuple[SurveyConclusionSummaryView, ...]
    next_created_at: datetime | None
    next_conclusion_id: uuid.UUID | None
    has_more: bool
