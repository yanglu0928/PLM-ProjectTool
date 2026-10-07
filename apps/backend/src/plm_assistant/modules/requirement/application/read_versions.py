"""Authorized immutable RequirementVersion summary and fixed snapshot reads."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class RequirementVersionReadError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RequirementVersionReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RequirementVersionSummary:
    requirement_version_id: uuid.UUID
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    title: str | None
    domain_name: str
    priority: str
    risk: str
    classification: str
    content_fingerprint: str
    declared_source_count: int
    declared_acceptance_count: int
    declared_capability_count: int
    declared_assumption_count: int
    declared_exclusion_count: int
    declared_dependency_count: int
    declared_ai_task_count: int
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RequirementSourceEvidenceView:
    evidence_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class RequirementSourceView:
    ordinal: int
    source_type: str
    source_object_id: uuid.UUID
    source_version_ref: uuid.UUID | None
    evidence_refs: tuple[RequirementSourceEvidenceView, ...]


@dataclass(frozen=True, slots=True)
class RequirementAcceptanceView:
    ordinal: int
    observable_result: str
    verification_method: str
    required_data: str
    required_environment: str
    evidence_requirement: str


@dataclass(frozen=True, slots=True)
class RequirementAssessmentEvidenceView:
    evidence_id: uuid.UUID
    evidence_role: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class RequirementCapabilityAssessmentView:
    ordinal: int
    baseline_version_id: uuid.UUID
    capability_item_id: uuid.UUID
    match_type: str
    fit_gap: str
    constraints_text: str
    assessor_kind: str
    assessed_by: uuid.UUID | None
    assessed_at: datetime
    confirmation_state: str
    evidence_refs: tuple[RequirementAssessmentEvidenceView, ...]


@dataclass(frozen=True, slots=True)
class RequirementTextItemView:
    ordinal: int
    text: str


@dataclass(frozen=True, slots=True)
class RequirementAITaskView:
    ai_task_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class RequirementVersionView:
    summary: RequirementVersionSummary
    statement: str
    rationale: str
    sources: tuple[RequirementSourceView, ...]
    acceptance_criteria: tuple[RequirementAcceptanceView, ...]
    capability_assessments: tuple[RequirementCapabilityAssessmentView, ...]
    assumptions: tuple[RequirementTextItemView, ...]
    exclusions: tuple[RequirementTextItemView, ...]
    dependencies: tuple[RequirementTextItemView, ...]
    ai_tasks: tuple[RequirementAITaskView, ...]


@dataclass(frozen=True, slots=True)
class RequirementVersionPage:
    items: tuple[RequirementVersionSummary, ...]
    next_version_no: int | None
    has_more: bool


class RequirementVersionReadRepositoryPort(Protocol):
    def list_versions(self, transaction: object, *, project_id: uuid.UUID,
                      requirement_id: uuid.UUID, after_version_no: int | None,
                      limit: int) -> tuple[RequirementVersionSummary, ...]: ...
    def get_version(self, transaction: object, *, project_id: uuid.UUID,
                    requirement_id: uuid.UUID,
                    requirement_version_id: uuid.UUID) -> RequirementVersionView | None: ...


class RequirementVersionReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: RequirementVersionReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("RequirementVersion read dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_versions(self, query: RequirementVersionReadQuery, *,
                      requirement_id: uuid.UUID, page_size: int,
                      after_version_no: int | None = None) -> RequirementVersionPage:
        self._validate_query(query)
        self._identity(requirement_id)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or after_version_no is not None and (
                    type(after_version_no) is not int or after_version_no < 1)):
            raise RequirementVersionReadError("VALIDATION_FAILED")
        def read(tx):
            rows = self._repository.list_versions(
                tx, project_id=query.project_id, requirement_id=requirement_id,
                after_version_no=after_version_no, limit=page_size + 1,
            )
            if (type(rows) is not tuple or len(rows) > page_size + 1
                    or any(type(row) is not RequirementVersionSummary for row in rows)):
                raise RequirementVersionReadError()
            items, more = rows[:page_size], len(rows) > page_size
            return RequirementVersionPage(
                items, items[-1].version_no if more else None, more,
            )
        return self._run(query, "REQ_VERSION_LIST", read)

    def get_version(self, query: RequirementVersionReadQuery, *,
                    requirement_id: uuid.UUID,
                    requirement_version_id: uuid.UUID) -> RequirementVersionView:
        self._validate_query(query)
        self._identity(requirement_id)
        self._identity(requirement_version_id)
        def read(tx):
            row = self._repository.get_version(
                tx, project_id=query.project_id, requirement_id=requirement_id,
                requirement_version_id=requirement_version_id,
            )
            if type(row) is not RequirementVersionView:
                raise RequirementVersionReadError("RESOURCE_NOT_FOUND")
            self._complete(row)
            return row
        return self._run(query, "REQ_VERSION_GET", read)

    def _run(self, query: RequirementVersionReadQuery, operation: str, read):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise RequirementVersionReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise RequirementVersionReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                if (authorized.user_id != actor or authorized.project_id != query.project_id
                        or authorized.operation != operation):
                    raise RequirementVersionReadError("RESOURCE_NOT_FOUND")
                return read(tx)
        except RequirementVersionReadError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementVersionReadError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementVersionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementVersionReadError() from None

    @staticmethod
    def _complete(view: RequirementVersionView) -> None:
        summary = view.summary
        pairs = (
            (view.sources, summary.declared_source_count),
            (view.acceptance_criteria, summary.declared_acceptance_count),
            (view.capability_assessments, summary.declared_capability_count),
            (view.assumptions, summary.declared_assumption_count),
            (view.exclusions, summary.declared_exclusion_count),
            (view.dependencies, summary.declared_dependency_count),
            (view.ai_tasks, summary.declared_ai_task_count),
        )
        if (len(summary.content_fingerprint) != 64
                or any(type(items) is not tuple or len(items) != count
                       or tuple(item.ordinal for item in items) != tuple(range(count))
                       for items, count in pairs)
                or any(tuple(item.ordinal for item in source.evidence_refs)
                       != tuple(range(len(source.evidence_refs)))
                       for source in view.sources)
                or any(tuple(item.ordinal for item in assessment.evidence_refs)
                       != tuple(range(len(assessment.evidence_refs)))
                       for assessment in view.capability_assessments)):
            raise RequirementVersionReadError()

    @staticmethod
    def _validate_query(query: RequirementVersionReadQuery) -> None:
        if (type(query) is not RequirementVersionReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0):
            raise RequirementVersionReadError("VALIDATION_FAILED")

    @staticmethod
    def _identity(value: uuid.UUID) -> None:
        if type(value) is not uuid.UUID or value.int == 0:
            raise RequirementVersionReadError("RESOURCE_NOT_FOUND")
