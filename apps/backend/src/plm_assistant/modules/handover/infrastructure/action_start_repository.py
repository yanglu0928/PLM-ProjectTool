"""Handover-owned OPEN to IN_PROGRESS transition persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update

from plm_assistant.modules.handover.application.start_action import (
    HandoverActionStartError, HandoverActionStartView, StartHandoverAction,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import HandoverActionItemRow, HandoverActionStateEventRow


class SqlAlchemyHandoverActionStartRepository:
    @staticmethod
    def _allowed(row, actor_id, actor_role):
        return actor_role == "PROJECT_MANAGER" or row.owner_ref == actor_id

    def start(self, transaction: object, *, command: StartHandoverAction,
              actor_id: uuid.UUID, actor_role: str,
              occurred_at: datetime) -> HandoverActionStartView:
        session = _session(transaction)
        row = session.execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == command.action_item_id,
            HandoverActionItemRow.project_id == command.project_id,
        ).with_for_update(of=HandoverActionItemRow)).scalar_one_or_none()
        if row is None or not self._allowed(row, actor_id, actor_role):
            raise HandoverActionStartError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise HandoverActionStartError("CONFLICT_VERSION")
        if row.action_state != "OPEN":
            raise HandoverActionStartError("HANDOVER_STATE_INVALID")
        event_id, version = uuid.UUID(new_uuid7()), row.lock_version + 1
        session.execute(insert(HandoverActionStateEventRow).values(
            action_state_event_id=event_id, action_item_id=row.action_item_id,
            project_id=row.project_id, sequence_no=version,
            from_state="OPEN", to_state="IN_PROGRESS", actor_id=actor_id,
            reason=command.reason, occurred_at=occurred_at, trace_id=command.trace_id,
        ))
        result = session.execute(update(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == row.action_item_id,
            HandoverActionItemRow.project_id == row.project_id,
            HandoverActionItemRow.lock_version == row.lock_version,
            HandoverActionItemRow.action_state == "OPEN",
        ).values(action_state="IN_PROGRESS", updated_by=actor_id,
                 updated_at=occurred_at, lock_version=version))
        if result.rowcount != 1:
            raise HandoverActionStartError("CONFLICT_VERSION")
        return HandoverActionStartView(
            row.action_item_id, row.project_id, event_id,
            "IN_PROGRESS", occurred_at, f'"v{version}"',
        )

    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID, actor_role: str) -> HandoverActionStartView | None:
        session = _session(transaction)
        row = session.execute(select(
            HandoverActionItemRow.owner_ref,
            HandoverActionStateEventRow.sequence_no,
            HandoverActionStateEventRow.occurred_at,
        ).join(
            HandoverActionStateEventRow,
            (HandoverActionStateEventRow.action_item_id == HandoverActionItemRow.action_item_id)
            & (HandoverActionStateEventRow.project_id == HandoverActionItemRow.project_id),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionStateEventRow.action_state_event_id == event_id,
            HandoverActionStateEventRow.from_state == "OPEN",
            HandoverActionStateEventRow.to_state == "IN_PROGRESS",
            HandoverActionStateEventRow.actor_id == actor_id,
        ).with_for_update(of=HandoverActionItemRow, read=True)).one_or_none()
        if row is None or not (actor_role == "PROJECT_MANAGER" or row.owner_ref == actor_id):
            raise HandoverActionStartError("RESOURCE_NOT_FOUND")
        return HandoverActionStartView(
            action_item_id, project_id, event_id, "IN_PROGRESS",
            row.occurred_at, f'"v{row.sequence_no}"',
        )
