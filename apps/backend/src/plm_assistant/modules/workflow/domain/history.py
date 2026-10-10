"""Immutable proposed history shape, never evidence of authorization/Gate approval.

Only an application service with same-transaction Owner proofs may persist these.
UUID references alone do not establish existence, scope, approval or integrity.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from .catalog_v1 import six_stage_definition
from .transition import ChecklistState


class WorkflowHistoryError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid Workflow history shape")


def _uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _refs(value: object, *, required: bool = True) -> bool:
    return (type(value) is tuple and (bool(value) or not required)
            and all(_uuid(ref) for ref in value)
            and len(set(value)) == len(value))


def _reason(value: object) -> bool:
    return (type(value) is str and 0 < len(value) <= 2000
            and bool(value.strip()) and "\x00" not in value)


@dataclass(frozen=True, slots=True)
class GateItemSnapshot:
    item_key: str
    result: ChecklistState
    evidence_refs: tuple[UUID, ...]
    review_round_refs: tuple[UUID, ...]
    exception_refs: tuple[UUID, ...] = ()
    waiver_actor_id: UUID | None = None
    waiver_reason: str | None = None
    waiver_impact: str | None = None

    def __post_init__(self) -> None:
        keys = {item.item_key for stage in six_stage_definition().stages
                for item in stage.checklist_items}
        if (type(self.item_key) is not str or self.item_key not in keys
                or type(self.result) is not ChecklistState
                or self.result not in (ChecklistState.PASS, ChecklistState.WAIVED)
                or not _refs(self.evidence_refs)
                or not _refs(self.review_round_refs)
                or not _refs(self.exception_refs, required=False)):
            raise WorkflowHistoryError()
        if self.result is ChecklistState.WAIVED:
            if (not self.exception_refs or not _uuid(self.waiver_actor_id)
                    or not _reason(self.waiver_reason)
                    or not _reason(self.waiver_impact)):
                raise WorkflowHistoryError()
        elif (self.exception_refs or self.waiver_actor_id is not None
              or self.waiver_reason is not None or self.waiver_impact is not None):
            raise WorkflowHistoryError()


@dataclass(frozen=True, slots=True)
class ForwardTransitionSnapshot:
    workflow_id: UUID
    project_id: UUID
    actor_id: UUID
    trace_id: UUID
    definition_version: int
    from_stage: str
    to_stage: str
    before_lock_version: int
    after_lock_version: int
    reason: str
    occurred_at: datetime
    gate_items: tuple[GateItemSnapshot, ...]

    def __post_init__(self) -> None:
        definition = six_stage_definition()
        keys = tuple(stage.stage_key for stage in definition.stages)
        if (not all(_uuid(value) for value in (
                self.workflow_id, self.project_id, self.actor_id, self.trace_id))
                or type(self.definition_version) is not int
                or self.definition_version != definition.version
                or type(self.from_stage) is not str or self.from_stage not in keys
                or type(self.to_stage) is not str
                or keys.index(self.from_stage) + 1 >= len(keys)
                or self.to_stage != keys[keys.index(self.from_stage) + 1]
                or type(self.before_lock_version) is not int
                or self.before_lock_version < 0
                or type(self.after_lock_version) is not int
                or self.after_lock_version != self.before_lock_version + 1
                or not _reason(self.reason)
                or type(self.occurred_at) is not datetime
                or self.occurred_at.tzinfo is None
                or self.occurred_at.utcoffset() != timedelta(0)
                or type(self.gate_items) is not tuple
                or any(type(item) is not GateItemSnapshot for item in self.gate_items)):
            raise WorkflowHistoryError()
        expected = tuple(item.item_key for item in
                         definition.stages[keys.index(self.from_stage)].checklist_items)
        if tuple(item.item_key for item in self.gate_items) != expected:
            raise WorkflowHistoryError()
        # Revalidate nested frozen objects; deserialization must not trust a bypassed init.
        for item in self.gate_items:
            item.__post_init__()
