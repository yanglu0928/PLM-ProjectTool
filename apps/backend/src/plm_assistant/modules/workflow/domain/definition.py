"""Versioned Workflow definition shape; no business stage catalog is implied."""

from __future__ import annotations

import re
from dataclasses import dataclass


_KEY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)


class WorkflowDefinitionError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid Workflow definition")


def _key(value: object) -> bool:
    return type(value) is str and _KEY.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class ChecklistItemDefinition:
    item_key: str
    required: bool
    evidence_policy_ref: str | None = None
    review_policy_ref: str | None = None

    def __post_init__(self) -> None:
        if (not _key(self.item_key) or type(self.required) is not bool
                or self.evidence_policy_ref is not None
                and not _key(self.evidence_policy_ref)
                or self.review_policy_ref is not None
                and not _key(self.review_policy_ref)):
            raise WorkflowDefinitionError()


@dataclass(frozen=True, slots=True)
class StageDefinition:
    stage_key: str
    order: int
    gate_policy_ref: str
    checklist_items: tuple[ChecklistItemDefinition, ...]

    def __post_init__(self) -> None:
        if (not _key(self.stage_key)
                or type(self.order) is not int or self.order <= 0
                or not _key(self.gate_policy_ref)
                or type(self.checklist_items) is not tuple
                or not self.checklist_items
                or any(type(item) is not ChecklistItemDefinition
                       for item in self.checklist_items)):
            raise WorkflowDefinitionError()
        keys = tuple(item.item_key for item in self.checklist_items)
        if len(set(keys)) != len(keys):
            raise WorkflowDefinitionError()


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    version: int
    stages: tuple[StageDefinition, ...]

    def __post_init__(self) -> None:
        if (type(self.version) is not int or self.version <= 0
                or type(self.stages) is not tuple or not self.stages
                or any(type(stage) is not StageDefinition for stage in self.stages)):
            raise WorkflowDefinitionError()
        keys = tuple(stage.stage_key for stage in self.stages)
        orders = tuple(stage.order for stage in self.stages)
        if (len(set(keys)) != len(keys)
                or len(set(orders)) != len(orders)
                or orders != tuple(sorted(orders))):
            raise WorkflowDefinitionError()
