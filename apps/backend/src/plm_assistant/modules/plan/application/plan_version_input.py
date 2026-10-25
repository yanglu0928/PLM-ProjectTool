"""Strict immutable PlanVersion draft input and structural validation.

This module is deliberately independent of SQLAlchemy and HTTP. It preserves
the frozen API-04 semantic fields and rejects unsupported output references
until an OutputArtifact owner exists.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    canonical_payload_fingerprint,
)


_ID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ITEM_STATES = {"NOT_STARTED", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"}
_SOLUTION_KINDS = {"OUTLINE", "SECTION", "STRUCTURED_SPEC"}
_EXCLUSION_KINDS = {
    "REQUIREMENT_VERSION", "SOLUTION_OUTLINE_VERSION",
    "SOLUTION_SECTION_VERSION", "STRUCTURED_SPEC_VERSION",
}


class PlanVersionInputError(RuntimeError):
    def __init__(self, code: str = "VALIDATION_FAILED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FixedVersionRef:
    resource_kind: str
    resource_id: uuid.UUID
    version_id: uuid.UUID
    spec_series_id: uuid.UUID | None = None
    spec_type: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementVersionRef:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanExclusionInput:
    target_kind: str
    resource_id: uuid.UUID
    version_id: uuid.UUID
    reason: str
    impact: str
    spec_series_id: uuid.UUID | None = None
    spec_type: str | None = None


@dataclass(frozen=True, slots=True)
class WbsItemInput:
    wbs_item_id: uuid.UUID
    parent_item_id: uuid.UUID | None
    wbs_code: str
    name: str
    level: int
    category: str
    owner_project_member_id: uuid.UUID | None
    support_role_refs: tuple[str, ...]
    planned_start: date | None
    planned_finish: date | None
    duration_minutes: int | None
    actual_start: date | None
    actual_finish: date | None
    item_state: str
    entry_conditions: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    requirement_refs: tuple[RequirementVersionRef, ...]
    solution_refs: tuple[FixedVersionRef, ...]
    prototype_refs: tuple[FixedVersionRef, ...]
    evidence_refs: tuple[uuid.UUID, ...]
    output_refs: tuple[uuid.UUID, ...]
    risk: str | None
    explicit_exclusion: str | None


@dataclass(frozen=True, slots=True)
class DependencyInput:
    dependency_id: uuid.UUID
    predecessor_item_id: uuid.UUID
    successor_item_id: uuid.UUID
    dependency_type: str
    lag: int
    lag_unit: str | None
    lag_reason: str | None


@dataclass(frozen=True, slots=True)
class MilestoneInput:
    name: str
    target_date: date
    duration_days: int
    acceptance_rule: str
    gate_ref: str | None
    wbs_item_refs: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class PlanVersionDraftInput:
    approved_solution_refs: tuple[FixedVersionRef, ...]
    wbs_items: tuple[WbsItemInput, ...]
    dependencies: tuple[DependencyInput, ...]
    milestones: tuple[MilestoneInput, ...]
    calendar_ref: str | None
    exclusions: tuple[PlanExclusionInput, ...]


@dataclass(frozen=True, slots=True)
class ValidatedPlanVersionDraft:
    input: PlanVersionDraftInput = field(repr=False)
    canonical_json: bytes = field(repr=False)
    request_fingerprint: bytes = field(repr=False)


def _invalid() -> None:
    raise PlanVersionInputError()


def _mapping(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        _invalid()
    if set(value) != keys:
        _invalid()
    return value


def _uuid(value: object, *, optional: bool = False) -> uuid.UUID | None:
    if optional and value is None:
        return None
    if type(value) is uuid.UUID and value.int:
        return value
    if type(value) is str and _ID_RE.fullmatch(value):
        try:
            result = uuid.UUID(value)
            if result.int:
                return result
        except ValueError:
            pass
    _invalid()


def _date(value: object, *, optional: bool = False) -> date | None:
    if optional and value is None:
        return None
    if type(value) is date:
        return value
    if type(value) is str:
        try:
            result = date.fromisoformat(value)
            if result.isoformat() == value:
                return result
        except ValueError:
            pass
    _invalid()


def _text(value: object, maximum: int, *, optional: bool = False,
          pattern: re.Pattern[str] | None = None) -> str | None:
    if optional and value is None:
        return None
    if type(value) is not str:
        _invalid()
    normalized = unicodedata.normalize("NFKC", value).strip()
    if (not 1 <= len(normalized) <= maximum
            or any(unicodedata.category(char)[0] == "C" for char in normalized)
            or (pattern is not None and pattern.fullmatch(normalized) is None)):
        _invalid()
    return normalized


def _int(value: object, *, minimum: int = 0, maximum: int = 2_147_483_647) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _invalid()
    return value


def _sequence(value: object, maximum: int = 10_000) -> tuple[object, ...]:
    if type(value) not in (list, tuple) or len(value) > maximum:
        _invalid()
    return tuple(value)


def _fixed_ref(value: object, *, allowed_kinds: set[str] = _SOLUTION_KINDS) -> FixedVersionRef:
    item = _mapping(value, {
        "resource_kind", "resource_id", "version_id", "spec_series_id", "spec_type",
    })
    kind = _text(item["resource_kind"], 32)
    if kind not in allowed_kinds:
        _invalid()
    resource_id = _uuid(item["resource_id"])
    version_id = _uuid(item["version_id"])
    series = _uuid(item["spec_series_id"], optional=True)
    spec_type = _text(item["spec_type"], 64, optional=True, pattern=_CODE_RE)
    if kind == "STRUCTURED_SPEC":
        if series is None or spec_type is None:
            _invalid()
    elif series is not None or spec_type is not None:
        _invalid()
    return FixedVersionRef(kind, resource_id, version_id, series, spec_type)


def _requirement_ref(value: object) -> RequirementVersionRef:
    item = _mapping(value, {"requirement_id", "requirement_version_id"})
    return RequirementVersionRef(
        _uuid(item["requirement_id"]), _uuid(item["requirement_version_id"]))


def _wbs_item(value: object) -> WbsItemInput:
    keys = {
        "wbs_item_id", "parent_item_id", "wbs_code", "name", "level", "category",
        "owner_ref", "support_role_refs", "planned_start", "planned_finish",
        "duration_minutes", "actual_start", "actual_finish", "item_state",
        "entry_conditions", "acceptance_criteria", "requirement_refs", "solution_refs",
        "prototype_refs", "evidence_refs", "output_refs", "risk", "explicit_exclusion",
    }
    item = _mapping(value, keys)
    requirement_refs = tuple(_requirement_ref(v) for v in _sequence(item["requirement_refs"], 500))
    solution_refs = tuple(_fixed_ref(v) for v in _sequence(item["solution_refs"], 500))
    prototype_refs = tuple(_fixed_ref(v, allowed_kinds={"PROTOTYPE"})
                           for v in _sequence(item["prototype_refs"], 500))
    evidence_refs = tuple(_uuid(v) for v in _sequence(item["evidence_refs"], 500))
    output_refs = tuple(_uuid(v) for v in _sequence(item["output_refs"], 500))
    if output_refs:
        raise PlanVersionInputError("OUTPUT_REFERENCE_UNAVAILABLE")
    if (len({v.requirement_id for v in requirement_refs}) != len(requirement_refs)
            or len({v.requirement_version_id for v in requirement_refs}) != len(requirement_refs)
            or len(set(solution_refs)) != len(solution_refs)
            or len(set(prototype_refs)) != len(prototype_refs)
            or len(set(evidence_refs)) != len(evidence_refs)
            or len(set(output_refs)) != len(output_refs)):
        _invalid()
    state = _text(item["item_state"], 32)
    category = _text(item["category"], 64, pattern=_CODE_RE)
    if state not in _ITEM_STATES:
        _invalid()
    planned_start = _date(item["planned_start"], optional=True)
    planned_finish = _date(item["planned_finish"], optional=True)
    actual_start = _date(item["actual_start"], optional=True)
    actual_finish = _date(item["actual_finish"], optional=True)
    if ((planned_start is None) != (planned_finish is None)
            or (actual_start is None) != (actual_finish is None)
            or (planned_finish is not None and planned_finish < planned_start)
            or (actual_finish is not None and actual_finish < actual_start)):
        _invalid()
    roles = tuple(_text(v, 64, pattern=_CODE_RE) for v in _sequence(item["support_role_refs"], 100))
    entries = tuple(_text(v, 2000) for v in _sequence(item["entry_conditions"], 500))
    criteria = tuple(_text(v, 2000) for v in _sequence(item["acceptance_criteria"], 500))
    if len(set(roles)) != len(roles) or len(set(entries)) != len(entries) or len(set(criteria)) != len(criteria):
        _invalid()
    return WbsItemInput(
        _uuid(item["wbs_item_id"]), _uuid(item["parent_item_id"], optional=True),
        _text(item["wbs_code"], 64), _text(item["name"], 500),
        _int(item["level"], minimum=1, maximum=6), category,
        _uuid(item["owner_ref"], optional=True), roles,
        planned_start, planned_finish,
        None if item["duration_minutes"] is None else _int(item["duration_minutes"]),
        actual_start, actual_finish, state, entries, criteria,
        requirement_refs, solution_refs, prototype_refs, evidence_refs, output_refs,
        _text(item["risk"], 2000, optional=True),
        _text(item["explicit_exclusion"], 2000, optional=True),
    )


def _dependency(value: object) -> DependencyInput:
    item = _mapping(value, {
        "dependency_id", "predecessor_item_id", "successor_item_id",
        "dependency_type", "lag", "lag_unit", "lag_reason",
    })
    kind = _text(item["dependency_type"], 8)
    lag = _int(item["lag"], maximum=365_000)
    lag_unit = _text(item["lag_unit"], 32, optional=True)
    lag_reason = _text(item["lag_reason"], 1000, optional=True)
    if kind != "FS" or (lag and (lag_unit is None or lag_reason is None)):
        _invalid()
    return DependencyInput(
        _uuid(item["dependency_id"]), _uuid(item["predecessor_item_id"]),
        _uuid(item["successor_item_id"]), kind, lag, lag_unit, lag_reason)


def _milestone(value: object) -> MilestoneInput:
    item = _mapping(value, {
        "name", "target_date", "duration_days", "acceptance_rule", "gate_ref", "wbs_item_refs",
    })
    refs = tuple(_uuid(v) for v in _sequence(item["wbs_item_refs"], 10_000))
    if len(set(refs)) != len(refs):
        _invalid()
    return MilestoneInput(
        _text(item["name"], 500), _date(item["target_date"]),
        _int(item["duration_days"], maximum=365_000),
        _text(item["acceptance_rule"], 2000),
        _text(item["gate_ref"], 128, optional=True), refs)


def _exclusion(value: object) -> PlanExclusionInput:
    item = _mapping(value, {
        "target_kind", "resource_id", "version_id", "reason", "impact",
        "spec_series_id", "spec_type",
    })
    kind = _text(item["target_kind"], 40)
    if kind not in _EXCLUSION_KINDS:
        _invalid()
    series = _uuid(item["spec_series_id"], optional=True)
    spec_type = _text(item["spec_type"], 64, optional=True, pattern=_CODE_RE)
    if (kind == "STRUCTURED_SPEC_VERSION") != (series is not None and spec_type is not None):
        _invalid()
    if kind != "STRUCTURED_SPEC_VERSION" and (series is not None or spec_type is not None):
        _invalid()
    return PlanExclusionInput(
        kind, _uuid(item["resource_id"]), _uuid(item["version_id"]),
        _text(item["reason"], 2000), _text(item["impact"], 2000), series, spec_type)


def _canonical(value: PlanVersionDraftInput) -> dict[str, object]:
    def fixed(ref: FixedVersionRef) -> dict[str, str | None]:
        return {"resource_kind": ref.resource_kind, "resource_id": str(ref.resource_id),
                "version_id": str(ref.version_id),
                "spec_series_id": str(ref.spec_series_id) if ref.spec_series_id else None,
                "spec_type": ref.spec_type}

    return {
        "approved_solution_refs": [fixed(ref) for ref in value.approved_solution_refs],
        "wbs_items": [{
            "wbs_item_id": str(item.wbs_item_id),
            "parent_item_id": str(item.parent_item_id) if item.parent_item_id else None,
            "wbs_code": item.wbs_code, "name": item.name, "level": item.level,
            "category": item.category,
            "owner_ref": str(item.owner_project_member_id) if item.owner_project_member_id else None,
            "support_role_refs": list(item.support_role_refs),
            "planned_start": item.planned_start.isoformat() if item.planned_start else None,
            "planned_finish": item.planned_finish.isoformat() if item.planned_finish else None,
            "duration_minutes": item.duration_minutes,
            "actual_start": item.actual_start.isoformat() if item.actual_start else None,
            "actual_finish": item.actual_finish.isoformat() if item.actual_finish else None,
            "item_state": item.item_state,
            "entry_conditions": list(item.entry_conditions),
            "acceptance_criteria": list(item.acceptance_criteria),
            "requirement_refs": [{"requirement_id": str(ref.requirement_id),
                                  "requirement_version_id": str(ref.requirement_version_id)}
                                 for ref in item.requirement_refs],
            "solution_refs": [fixed(ref) for ref in item.solution_refs],
            "prototype_refs": [fixed(ref) for ref in item.prototype_refs],
            "evidence_refs": [str(ref) for ref in item.evidence_refs],
            "output_refs": [str(ref) for ref in item.output_refs],
            "risk": item.risk, "explicit_exclusion": item.explicit_exclusion,
        } for item in value.wbs_items],
        "dependencies": [{
            "dependency_id": str(item.dependency_id),
            "predecessor_item_id": str(item.predecessor_item_id),
            "successor_item_id": str(item.successor_item_id),
            "dependency_type": item.dependency_type, "lag": item.lag,
            "lag_unit": item.lag_unit, "lag_reason": item.lag_reason,
        } for item in value.dependencies],
        "milestones": [{"name": item.name, "target_date": item.target_date.isoformat(),
                        "duration_days": item.duration_days,
                        "acceptance_rule": item.acceptance_rule,
                        "gate_ref": item.gate_ref,
                        "wbs_item_refs": [str(ref) for ref in item.wbs_item_refs]}
                       for item in value.milestones],
        "calendar_ref": value.calendar_ref,
        "exclusions": [{"target_kind": item.target_kind,
                        "resource_id": str(item.resource_id),
                        "version_id": str(item.version_id), "reason": item.reason,
                        "impact": item.impact,
                        "spec_series_id": str(item.spec_series_id) if item.spec_series_id else None,
                        "spec_type": item.spec_type} for item in value.exclusions],
    }


def parse_plan_version_draft(value: object, *, project_id: uuid.UUID,
                              plan_id: uuid.UUID) -> ValidatedPlanVersionDraft:
    """Parse an exact JSON-like mapping, normalize values and validate structure."""
    if (type(project_id) is not uuid.UUID or not project_id.int
            or type(plan_id) is not uuid.UUID or not plan_id.int):
        _invalid()
    item = _mapping(value, {
        "approved_solution_refs", "wbs_items", "dependencies", "milestones",
        "calendar_ref", "exclusions",
    })
    approved = tuple(_fixed_ref(v) for v in _sequence(item["approved_solution_refs"], 500))
    if not approved:
        _invalid()
    wbs = tuple(_wbs_item(v) for v in _sequence(item["wbs_items"], 10_000))
    dependencies = tuple(_dependency(v) for v in _sequence(item["dependencies"], 20_000))
    milestones = tuple(_milestone(v) for v in _sequence(item["milestones"], 2_000))
    exclusions = tuple(_exclusion(v) for v in _sequence(item["exclusions"], 2_000))
    calendar_ref = _text(item["calendar_ref"], 128, optional=True, pattern=_CODE_RE)
    value = PlanVersionDraftInput(approved, wbs, dependencies, milestones, calendar_ref, exclusions)

    if (len(set(approved)) != len(approved)
            or len({(x.target_kind, x.resource_id, x.version_id) for x in exclusions}) != len(exclusions)):
        _invalid()
    ids = [item.wbs_item_id for item in wbs]
    by_id = {item.wbs_item_id: item for item in wbs}
    if len(by_id) != len(ids) or len({item.wbs_code for item in wbs}) != len(wbs):
        _invalid()
    for current in wbs:
        if current.parent_item_id is None:
            if current.level != 1:
                _invalid()
        else:
            parent = by_id.get(current.parent_item_id)
            if parent is None or current.level != parent.level + 1:
                _invalid()
    edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
    graph: dict[uuid.UUID, list[uuid.UUID]] = {key: [] for key in by_id}
    dependency_ids: set[uuid.UUID] = set()
    in_degree = {key: 0 for key in by_id}
    for dependency in dependencies:
        edge = (dependency.predecessor_item_id, dependency.successor_item_id)
        if (dependency.dependency_id in dependency_ids
                or edge in edges or edge[0] == edge[1]
                or edge[0] not in by_id or edge[1] not in by_id):
            _invalid()
        dependency_ids.add(dependency.dependency_id)
        edges.add(edge)
        graph[edge[0]].append(edge[1])
        in_degree[edge[1]] += 1
    ready = [node for node, count in in_degree.items() if count == 0]
    visited_count = 0
    while ready:
        node = ready.pop()
        visited_count += 1
        for child in graph[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                ready.append(child)
    if visited_count != len(graph):
        _invalid()
    if len({item.name for item in milestones}) != len(milestones):
        _invalid()
    for milestone in milestones:
        if any(ref not in by_id for ref in milestone.wbs_item_refs):
            _invalid()
    for current in wbs:
        if any(ref not in approved for ref in current.solution_refs):
            _invalid()

    canonical = _canonical(value)
    try:
        encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > 8_000_000:
            _invalid()
        fingerprint = canonical_payload_fingerprint({
            "project_id": str(project_id), "plan_id": str(plan_id),
            "plan_version_input": canonical,
        })
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError, IdempotencyError):
        _invalid()
    return ValidatedPlanVersionDraft(value, encoded, fingerprint)
