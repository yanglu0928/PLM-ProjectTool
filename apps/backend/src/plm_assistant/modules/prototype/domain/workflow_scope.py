"""Pure complete-scope rules; callers must independently prove every fact.

These candidate values are not authorization, Review proof, Evidence proof, or a
Workflow PASS. The application Owner must lock and re-prove their sources in one
transaction before using a successful partition.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


class PrototypeWorkflowScopeError(ValueError):
    """The candidate set cannot establish complete Prototype scope."""


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ids(values: object, *, nonempty: bool = True) -> bool:
    return (type(values) is tuple and (bool(values) or not nonempty)
            and all(_id(value) for value in values)
            and len(set(values)) == len(values))


def _text(value: object) -> bool:
    return (type(value) is str and bool(value) and value == value.strip()
            and "\x00" not in value)


@dataclass(frozen=True, slots=True)
class CurrentRequirementCandidate:
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    acceptance_criterion_refs: tuple[uuid.UUID, ...]

    def __post_init__(self) -> None:
        if (not _id(self.project_id) or not _id(self.requirement_id)
                or not _id(self.requirement_version_id)
                or not _ids(self.acceptance_criterion_refs)):
            raise PrototypeWorkflowScopeError()


@dataclass(frozen=True, slots=True)
class NotRequiredDecisionCandidate:
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    decision_id: uuid.UUID
    affected_requirement_version_refs: tuple[uuid.UUID, ...]
    confirmed_by: uuid.UUID
    reason: str
    impact: str

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.project_id, self.prototype_id, self.decision_id,
                self.confirmed_by))
                or not _ids(self.affected_requirement_version_refs)
                or not _text(self.reason) or not _text(self.impact)):
            raise PrototypeWorkflowScopeError()


@dataclass(frozen=True, slots=True)
class ApprovedPrototypeCandidate:
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    prototype_version_id: uuid.UUID
    current_approved_version_ref: uuid.UUID
    requirement_version_refs: tuple[uuid.UUID, ...]
    prototype_state: str
    version_state: str

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.project_id, self.prototype_id,
                self.prototype_version_id, self.current_approved_version_ref))
                or not _ids(self.requirement_version_refs)
                or self.prototype_state != "ACTIVE"
                or self.version_state != "APPROVED"
                or self.current_approved_version_ref != self.prototype_version_id):
            raise PrototypeWorkflowScopeError()


@dataclass(frozen=True, slots=True)
class CoverageLinkCandidate:
    project_id: uuid.UUID
    requirement_version_id: uuid.UUID
    prototype_version_id: uuid.UUID
    purpose: str
    covered_acceptance_criterion_refs: tuple[uuid.UUID, ...]
    uncovered_acceptance_criterion_refs: tuple[uuid.UUID, ...]
    link_state: str

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.project_id, self.requirement_version_id,
                self.prototype_version_id))
                or self.purpose not in {
                    "ILLUSTRATES", "VALIDATES", "ACCEPTANCE_REFERENCE",
                }
                or self.link_state != "ACTIVE"
                or not _ids(self.covered_acceptance_criterion_refs)
                or not _ids(self.uncovered_acceptance_criterion_refs,
                            nonempty=False)
                or set(self.covered_acceptance_criterion_refs)
                   & set(self.uncovered_acceptance_criterion_refs)):
            raise PrototypeWorkflowScopeError()


@dataclass(frozen=True, slots=True)
class PrototypeScopePartition:
    project_id: uuid.UUID
    requirements: tuple[CurrentRequirementCandidate, ...]
    decisions: tuple[NotRequiredDecisionCandidate, ...]
    prototypes: tuple[ApprovedPrototypeCandidate, ...]
    required_requirement_version_refs: tuple[uuid.UUID, ...]
    not_required_requirement_version_refs: tuple[uuid.UUID, ...]

    @property
    def all_not_required(self) -> bool:
        return not self.required_requirement_version_refs


def partition_current_scope(
    *, project_id: uuid.UUID,
    requirements: tuple[CurrentRequirementCandidate, ...],
    decisions: tuple[NotRequiredDecisionCandidate, ...],
    prototypes: tuple[ApprovedPrototypeCandidate, ...],
) -> PrototypeScopePartition:
    """Require every current approved RequirementVersion on exactly one side."""
    if (not _id(project_id) or type(requirements) is not tuple
            or not requirements or type(decisions) is not tuple
            or type(prototypes) is not tuple):
        raise PrototypeWorkflowScopeError()
    for values, expected in (
        (requirements, CurrentRequirementCandidate),
        (decisions, NotRequiredDecisionCandidate),
        (prototypes, ApprovedPrototypeCandidate),
    ):
        if any(type(value) is not expected for value in values):
            raise PrototypeWorkflowScopeError()
        for value in values:
            value.__post_init__()
            if value.project_id != project_id:
                raise PrototypeWorkflowScopeError()
    requirement_ids = [value.requirement_id for value in requirements]
    current_versions = [value.requirement_version_id for value in requirements]
    if (len(set(requirement_ids)) != len(requirement_ids)
            or len(set(current_versions)) != len(current_versions)
            or len({value.decision_id for value in decisions}) != len(decisions)
            or len({value.prototype_id for value in decisions}) != len(decisions)
            or len({value.prototype_id for value in prototypes}) != len(prototypes)
            or len({value.prototype_version_id for value in prototypes})
               != len(prototypes)
            or {value.prototype_id for value in decisions}
               & {value.prototype_id for value in prototypes}):
        raise PrototypeWorkflowScopeError()
    current = set(current_versions)
    not_required = [ref for decision in decisions
                    for ref in decision.affected_requirement_version_refs]
    required = {ref for prototype in prototypes
                for ref in prototype.requirement_version_refs}
    if (len(set(not_required)) != len(not_required)
            or not set(not_required).issubset(current)
            or not required.issubset(current)
            or set(not_required) & required
            or set(not_required) | required != current):
        raise PrototypeWorkflowScopeError()
    return PrototypeScopePartition(
        project_id, requirements, decisions, prototypes,
        tuple(sorted(required, key=lambda value: value.int)),
        tuple(sorted(not_required, key=lambda value: value.int)),
    )


def require_complete_coverage(
    partition: PrototypeScopePartition,
    links: tuple[CoverageLinkCandidate, ...],
) -> None:
    """Require current approved links to cover every required criterion."""
    if (type(partition) is not PrototypeScopePartition
            or type(links) is not tuple):
        raise PrototypeWorkflowScopeError()
    criteria = {value.requirement_version_id: set(value.acceptance_criterion_refs)
                for value in partition.requirements}
    approved = {value.prototype_version_id: set(value.requirement_version_refs)
                for value in partition.prototypes}
    covered: dict[uuid.UUID, set[uuid.UUID]] = {
        ref: set() for ref in partition.required_requirement_version_refs
    }
    for link in links:
        if type(link) is not CoverageLinkCandidate:
            raise PrototypeWorkflowScopeError()
        link.__post_init__()
        allowed = criteria.get(link.requirement_version_id)
        if (link.project_id != partition.project_id or allowed is None
                or link.requirement_version_id not in covered
                or link.requirement_version_id not in approved.get(
                    link.prototype_version_id, set())
                or set(link.covered_acceptance_criterion_refs)
                   | set(link.uncovered_acceptance_criterion_refs) != allowed):
            raise PrototypeWorkflowScopeError()
        if link.purpose in {"VALIDATES", "ACCEPTANCE_REFERENCE"}:
            covered[link.requirement_version_id].update(
                link.covered_acceptance_criterion_refs)
    if any(covered[ref] != criteria[ref] for ref in covered):
        raise PrototypeWorkflowScopeError()
