"""CR-WFL-004 immutable record shape; never authorization or approved facts.

Review references are resolved by the server, not new public request fields.
The application must prove current stage, chain and every Owner fact in its
transaction; UUIDs and construction success alone never satisfy a Gate.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from .catalog_v1 import six_stage_definition
from .history import _reason, _refs, _uuid
from .transition import ChecklistState


class ChecklistRecordError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid Checklist record shape")


def _version_pair(before: object, after: object) -> bool:
    return (type(before) is int and type(after) is int
            and 0 <= before < 2**63-1 and after == before+1)


@dataclass(frozen=True, slots=True)
class ChecklistRecordSnapshot:
    record_id: UUID
    workflow_id: UUID
    project_id: UUID
    actor_id: UUID
    trace_id: UUID
    definition_version: int
    stage_key: str
    item_key: str
    before_state: ChecklistState
    result: ChecklistState
    before_item_version: int
    after_item_version: int
    before_workflow_version: int
    after_workflow_version: int
    occurred_at: datetime
    supersedes_record_id: UUID | None = None
    evidence_refs: tuple[UUID, ...] = ()
    review_round_refs: tuple[UUID, ...] = ()
    exception_refs: tuple[UUID, ...] = ()
    reason: str | None = None
    impact: str | None = None

    def __post_init__(self) -> None:
        definition = six_stage_definition()
        owners = {item.item_key: stage.stage_key for stage in definition.stages
                  for item in stage.checklist_items}
        if (not all(_uuid(value) for value in (
                self.record_id, self.workflow_id, self.project_id, self.actor_id, self.trace_id))
                or type(self.definition_version) is not int
                or self.definition_version != definition.version
                or type(self.item_key) is not str or self.item_key not in owners
                or type(self.stage_key) is not str or owners[self.item_key] != self.stage_key
                or type(self.before_state) is not ChecklistState
                or type(self.result) is not ChecklistState
                or self.result not in (ChecklistState.PASS, ChecklistState.FAIL, ChecklistState.WAIVED)
                or not _version_pair(self.before_item_version, self.after_item_version)
                or not _version_pair(self.before_workflow_version, self.after_workflow_version)
                or type(self.occurred_at) is not datetime or self.occurred_at.tzinfo is None
                or self.occurred_at.utcoffset() != timedelta(0)
                or not _refs(self.evidence_refs, required=False)
                or not _refs(self.review_round_refs, required=False)
                or not _refs(self.exception_refs, required=False)
                or self.reason is not None and not _reason(self.reason)
                or self.impact is not None and not _reason(self.impact)):
            raise ChecklistRecordError()
        if self.before_item_version == 0:
            if self.before_state is not ChecklistState.PENDING or self.supersedes_record_id is not None:
                raise ChecklistRecordError()
        elif (self.before_state is ChecklistState.PENDING
              or not _uuid(self.supersedes_record_id)
              or self.supersedes_record_id == self.record_id):
            raise ChecklistRecordError()
        if self.result in (ChecklistState.PASS, ChecklistState.WAIVED):
            if not self.evidence_refs or not self.review_round_refs:
                raise ChecklistRecordError()
        if self.result is ChecklistState.WAIVED:
            if not self.exception_refs or self.reason is None or self.impact is None:
                raise ChecklistRecordError()
        elif self.exception_refs:
            raise ChecklistRecordError()
