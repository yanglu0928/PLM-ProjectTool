"""Pure, immutable PlanVersion validation report contract and evaluator."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .plan_version_input import (
    FixedVersionRef, PlanVersionDraftInput, RequirementVersionRef,
)


class PlanVersionValidationContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlanVersionValidationSnapshot:
    project_id: uuid.UUID
    plan_id: uuid.UUID
    plan_version_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: bytes
    draft: PlanVersionDraftInput


@dataclass(frozen=True, slots=True)
class PlanVersionCoverageSummary:
    requirement_total: int
    requirement_mapped: int
    requirement_excluded: int
    requirement_uncovered: int
    solution_total: int
    solution_mapped: int
    solution_excluded: int
    solution_uncovered: int

    def __post_init__(self) -> None:
        values = (
            self.requirement_total, self.requirement_mapped,
            self.requirement_excluded, self.requirement_uncovered,
            self.solution_total, self.solution_mapped,
            self.solution_excluded, self.solution_uncovered,
        )
        if (any(type(value) is not int or value < 0 for value in values)
                or any(value > total for value, total in (
                    (self.requirement_mapped, self.requirement_total),
                    (self.requirement_excluded, self.requirement_total),
                    (self.requirement_uncovered, self.requirement_total),
                    (self.solution_mapped, self.solution_total),
                    (self.solution_excluded, self.solution_total),
                    (self.solution_uncovered, self.solution_total)))):
            raise PlanVersionValidationContractError("invalid coverage summary")


@dataclass(frozen=True, slots=True)
class PlanVersionValidationReport:
    valid: bool
    blocking_issues: tuple[str, ...]
    warnings: tuple[str, ...]
    coverage_summary: PlanVersionCoverageSummary
    checked_at: datetime

    def __post_init__(self) -> None:
        if (type(self.valid) is not bool
                or type(self.blocking_issues) is not tuple
                or any(type(item) is not str or not item for item in self.blocking_issues)
                or self.blocking_issues != tuple(sorted(set(self.blocking_issues)))
                or type(self.warnings) is not tuple
                or any(type(item) is not str or not item for item in self.warnings)
                or type(self.coverage_summary) is not PlanVersionCoverageSummary
                or type(self.checked_at) is not datetime
                or self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None
                or self.valid != (not self.blocking_issues)):
            raise PlanVersionValidationContractError("invalid PlanVersion validation report")


def evaluate_plan_version(
    snapshot: PlanVersionValidationSnapshot,
    *,
    source_requirement_refs: tuple[RequirementVersionRef, ...],
    source_solution_refs: tuple[FixedVersionRef, ...],
    checked_at: datetime,
) -> PlanVersionValidationReport:
    """Evaluate only the supplied fixed snapshot and trusted source scope.

    No clock, I/O, authorization, or mutable business state is consulted here.
    Callers provide the current approved source scope from an authorized proof.
    """
    _validate_contract(snapshot, source_requirement_refs, source_solution_refs, checked_at)
    draft = snapshot.draft
    issues: set[str] = set()
    items = draft.wbs_items
    by_id = {item.wbs_item_id: item for item in items}
    if not items:
        issues.add("WBS_EMPTY")
    if len(by_id) != len(items):
        issues.add("WBS_ITEM_ID_DUPLICATE")
    if len({item.wbs_code for item in items}) != len(items):
        issues.add("WBS_CODE_DUPLICATE")

    for item in items:
        if item.level < 1 or item.level > 6:
            issues.add("WBS_HIERARCHY_INVALID")
        if item.parent_item_id is None:
            if item.level != 1:
                issues.add("WBS_HIERARCHY_INVALID")
        else:
            parent = by_id.get(item.parent_item_id)
            if parent is None or item.level != parent.level + 1:
                issues.add("WBS_HIERARCHY_INVALID")
        if ((item.planned_start is None) != (item.planned_finish is None)
                or (item.actual_start is None) != (item.actual_finish is None)
                or (item.planned_start is not None
                    and item.planned_finish < item.planned_start)
                or (item.actual_start is not None
                    and item.actual_finish < item.actual_start)):
            issues.add("WBS_DATE_RANGE_INVALID")

    edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
    dependency_ids: set[uuid.UUID] = set()
    graph: dict[uuid.UUID, list[uuid.UUID]] = {item_id: [] for item_id in by_id}
    in_degree = {item_id: 0 for item_id in by_id}
    for dependency in draft.dependencies:
        edge = dependency.predecessor_item_id, dependency.successor_item_id
        if (dependency.dependency_id in dependency_ids
                or edge[0] == edge[1] or edge[0] not in by_id or edge[1] not in by_id
                or edge in edges or dependency.dependency_type != "FS"):
            issues.add("DEPENDENCY_INVALID")
            continue
        dependency_ids.add(dependency.dependency_id)
        edges.add(edge)
        graph[edge[0]].append(edge[1])
        in_degree[edge[1]] += 1
    ready = sorted((item_id for item_id, count in in_degree.items() if count == 0),
                   key=str, reverse=True)
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for successor in graph[current]:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                ready.append(successor)
    if visited != len(graph):
        issues.add("DEPENDENCY_CYCLE")
    if any(any(ref not in by_id for ref in milestone.wbs_item_refs)
           for milestone in draft.milestones):
        issues.add("MILESTONE_WBS_REFERENCE_INVALID")

    coverage = _coverage(draft, source_requirement_refs, source_solution_refs, issues)
    blocking = tuple(sorted(issues))
    return PlanVersionValidationReport(
        valid=not blocking, blocking_issues=blocking, warnings=(),
        coverage_summary=coverage, checked_at=checked_at.astimezone(timezone.utc),
    )


def _coverage(
    draft: PlanVersionDraftInput,
    source_requirement_refs: tuple[RequirementVersionRef, ...],
    source_solution_refs: tuple[FixedVersionRef, ...],
    issues: set[str],
) -> PlanVersionCoverageSummary:
    source_requirements = {
        (ref.requirement_id, ref.requirement_version_id)
        for ref in source_requirement_refs
    }
    mapped_requirements = {
        (ref.requirement_id, ref.requirement_version_id)
        for item in draft.wbs_items for ref in item.requirement_refs
    }
    excluded_requirements = {
        (item.resource_id, item.version_id) for item in draft.exclusions
        if item.target_kind == "REQUIREMENT_VERSION"
    }
    if mapped_requirements - source_requirements:
        issues.add("REQUIREMENT_SOURCE_STALE")
    if excluded_requirements - source_requirements:
        issues.add("REQUIREMENT_SOURCE_STALE")
    if mapped_requirements & excluded_requirements:
        issues.add("REQUIREMENT_DISPOSITION_CONFLICT")

    source_solutions = set(source_solution_refs)
    if set(draft.approved_solution_refs) != source_solutions:
        issues.add("SOLUTION_SOURCE_STALE")
    mapped_solutions = {ref for item in draft.wbs_items for ref in item.solution_refs}
    excluded_solutions = {_solution_exclusion(item) for item in draft.exclusions}
    excluded_solutions.discard(None)
    if mapped_solutions - source_solutions or excluded_solutions - source_solutions:
        issues.add("SOLUTION_SOURCE_STALE")
    if mapped_solutions & excluded_solutions:
        issues.add("SOLUTION_DISPOSITION_CONFLICT")

    requirement_covered = (mapped_requirements | excluded_requirements) & source_requirements
    solution_covered = (mapped_solutions | excluded_solutions) & source_solutions
    if source_requirements - requirement_covered:
        issues.add("REQUIREMENT_UNCOVERED")
    if source_solutions - solution_covered:
        issues.add("SOLUTION_UNCOVERED")
    return PlanVersionCoverageSummary(
        requirement_total=len(source_requirements),
        requirement_mapped=len(mapped_requirements & source_requirements),
        requirement_excluded=len(excluded_requirements & source_requirements),
        requirement_uncovered=len(source_requirements - requirement_covered),
        solution_total=len(source_solutions),
        solution_mapped=len(mapped_solutions & source_solutions),
        solution_excluded=len(excluded_solutions & source_solutions),
        solution_uncovered=len(source_solutions - solution_covered),
    )


def _solution_exclusion(value: object) -> FixedVersionRef | None:
    mapping = {
        "SOLUTION_OUTLINE_VERSION": "OUTLINE",
        "SOLUTION_SECTION_VERSION": "SECTION",
        "STRUCTURED_SPEC_VERSION": "STRUCTURED_SPEC",
    }
    kind = mapping.get(value.target_kind)
    if kind is None:
        return None
    return FixedVersionRef(kind, value.resource_id, value.version_id,
                           value.spec_series_id, value.spec_type)


def _validate_contract(
    snapshot: PlanVersionValidationSnapshot,
    requirements: tuple[RequirementVersionRef, ...],
    solutions: tuple[FixedVersionRef, ...],
    checked_at: datetime,
) -> None:
    if (type(snapshot) is not PlanVersionValidationSnapshot
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                snapshot.project_id, snapshot.plan_id, snapshot.plan_version_id))
            or type(snapshot.version_no) is not int or snapshot.version_no < 1
            or type(snapshot.version_state) is not str or not snapshot.version_state
            or type(snapshot.content_fingerprint) is not bytes
            or len(snapshot.content_fingerprint) != 32
            or type(snapshot.draft) is not PlanVersionDraftInput
            or type(requirements) is not tuple
            or any(type(item) is not RequirementVersionRef for item in requirements)
            or type(solutions) is not tuple
            or any(type(item) is not FixedVersionRef for item in solutions)
            or type(checked_at) is not datetime or checked_at.tzinfo is None
            or checked_at.utcoffset() is None):
        raise PlanVersionValidationContractError("invalid PlanVersion validation input")
