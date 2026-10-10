"""Handover-owned nonterminal to CANCELLED persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update

from plm_assistant.modules.handover.application.cancel_action import (
    CancelHandoverAction, HandoverActionCancelError,
    HandoverActionCancelView,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import HandoverActionItemRow, HandoverActionStateEventRow


_NONTERMINAL = frozenset({"OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED"})


class SqlAlchemyHandoverActionCancelRepository:
    def cancel(self, transaction: object, *, command: CancelHandoverAction,
               actor_id: uuid.UUID, actor_role: str,
               occurred_at: datetime) -> HandoverActionCancelView:
        session = _session(transaction)
        row = session.execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == command.action_item_id,
            HandoverActionItemRow.project_id == command.project_id,
        ).with_for_update(of=HandoverActionItemRow)).scalar_one_or_none()
        if row is None or actor_role != "PROJECT_MANAGER":
            raise HandoverActionCancelError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise HandoverActionCancelError("CONFLICT_VERSION")
        if row.action_state not in _NONTERMINAL:
            raise HandoverActionCancelError("HANDOVER_ACTION_STATE_INVALID")
        previous, event_id = row.action_state, uuid.UUID(new_uuid7())
        version = row.lock_version + 1
        session.execute(insert(HandoverActionStateEventRow).values(
            action_state_event_id=event_id,
            action_item_id=row.action_item_id, project_id=row.project_id,
            sequence_no=version, from_state=previous, to_state="CANCELLED",
            actor_id=actor_id, reason=command.reason, occurred_at=occurred_at,
            trace_id=command.trace_id,
        ))
        changed = session.execute(update(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == row.action_item_id,
            HandoverActionItemRow.project_id == row.project_id,
            HandoverActionItemRow.lock_version == row.lock_version,
            HandoverActionItemRow.action_state == previous,
        ).values(
            action_state="CANCELLED", updated_by=actor_id,
            updated_at=occurred_at, lock_version=version,
        ))
        if changed.rowcount != 1:
            raise HandoverActionCancelError("CONFLICT_VERSION")
        return HandoverActionCancelView(
            row.action_item_id, row.project_id, event_id, "CANCELLED",
            previous, command.reason, occurred_at, f'"v{version}"',
        )

    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID,
               actor_role: str) -> HandoverActionCancelView | None:
        session = _session(transaction)
        row = session.execute(select(
            HandoverActionStateEventRow.sequence_no,
            HandoverActionStateEventRow.from_state,
            HandoverActionStateEventRow.reason,
            HandoverActionStateEventRow.occurred_at,
        ).join(
            HandoverActionItemRow,
            (HandoverActionItemRow.action_item_id
             == HandoverActionStateEventRow.action_item_id)
            & (HandoverActionItemRow.project_id
               == HandoverActionStateEventRow.project_id),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionStateEventRow.action_state_event_id == event_id,
            HandoverActionStateEventRow.to_state == "CANCELLED",
            HandoverActionStateEventRow.actor_id == actor_id,
        ).with_for_update(
            of=HandoverActionItemRow, read=True,
        )).one_or_none()
        if (row is None or actor_role != "PROJECT_MANAGER"
                or row.from_state not in _NONTERMINAL):
            raise HandoverActionCancelError("RESOURCE_NOT_FOUND")
        return HandoverActionCancelView(
            action_item_id, project_id, event_id, "CANCELLED",
            row.from_state, row.reason, row.occurred_at,
            f'"v{row.sequence_no}"',
        )
