"""Caller-transaction values for one immutable Checklist record append."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.transition import ChecklistState

from .current_checklist_record import ChecklistBasisObservation


class ChecklistRecordAppendError(RuntimeError):
    def __init__(self, code: str = "WORKFLOW_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


@dataclass(frozen=True, slots=True)
class ChecklistRecordWriteLock:
    workflow_id: uuid.UUID
    project_id: uuid.UUID
    definition_version: int
    stage_key: str
    stage_state: str
    item_key: str
    before_state: ChecklistState
    before_item_version: int
    before_workflow_version: int
    supersedes_record_id: uuid.UUID | None

    def __post_init__(self) -> None:
        definition = six_stage_definition(1)
        owners = {
            item.item_key: stage.stage_key
            for stage in definition.stages for item in stage.checklist_items
        }
        if type(self.before_item_version) is int:
            if self.before_item_version == 0:
                chain_valid = (
                    self.before_state is ChecklistState.PENDING
                    and self.supersedes_record_id is None
                )
            else:
                chain_valid = (
                    self.before_state is not ChecklistState.PENDING
                    and _id(self.supersedes_record_id)
                )
        else:
            chain_valid = False
        if (not _id(self.workflow_id) or not _id(self.project_id)
                or type(self.definition_version) is not int
                or self.definition_version != definition.version
                or self.item_key not in owners
                or owners[self.item_key] != self.stage_key
                or self.stage_state not in {"ACTIVE", "BLOCKED"}
                or type(self.before_state) is not ChecklistState
                or type(self.before_item_version) is not int
                or not 0 <= self.before_item_version < 2**63 - 1
                or type(self.before_workflow_version) is not int
                or not 0 <= self.before_workflow_version < 2**63 - 1
                or not chain_valid):
            raise ChecklistRecordAppendError("WORKFLOW_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class AppendChecklistRecord:
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    result: ChecklistState
    basis: tuple[ChecklistBasisObservation, ...]
    occurred_at: datetime
    reason: str | None = None
    impact: str | None = None

    def __post_init__(self) -> None:
        if (not _id(self.actor_id) or not _id(self.trace_id)
                or self.result not in {
                    ChecklistState.PASS, ChecklistState.FAIL,
                    ChecklistState.WAIVED,
                }
                or type(self.basis) is not tuple
                or any(type(value) is not ChecklistBasisObservation
                       for value in self.basis)
                or type(self.occurred_at) is not datetime
                or self.occurred_at.tzinfo is None
                or self.occurred_at.utcoffset() != timedelta(0)):
            raise ChecklistRecordAppendError("VALIDATION_FAILED")
        identities: set[tuple[str, uuid.UUID]] = set()
        positions: list[tuple[str, str]] = []
        for value in self.basis:
            try:
                value.__post_init__()
            except ValueError:
                raise ChecklistRecordAppendError("VALIDATION_FAILED") from None
            identity = (value.ref_kind, value.ref_id)
            if identity in identities:
                raise ChecklistRecordAppendError("VALIDATION_FAILED")
            identities.add(identity)
            positions.append((value.ref_kind, str(value.ref_id)))
        if positions != sorted(positions):
            raise ChecklistRecordAppendError("VALIDATION_FAILED")
