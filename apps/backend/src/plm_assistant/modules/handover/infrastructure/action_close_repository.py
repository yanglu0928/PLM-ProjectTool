"""Handover-owned VERIFIED to CLOSED persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update

from plm_assistant.modules.handover.application.close_action import (
    CloseHandoverAction, HandoverActionCloseError, HandoverActionCloseLock,
    HandoverActionCloseView,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import (
    HandoverActionItemRow, HandoverActionStateEventRow,
    HandoverAnalysisVersionRow,
)


class SqlAlchemyHandoverActionCloseRepository:
    def lock(self, transaction: object, *, command: CloseHandoverAction,
             actor_id: uuid.UUID,
             actor_role: str) -> HandoverActionCloseLock:
        session = _session(transaction)
        row = session.execute(select(
            HandoverActionItemRow,
            HandoverAnalysisVersionRow.handover_analysis_id,
        ).outerjoin(
            HandoverAnalysisVersionRow,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == HandoverActionItemRow.source_analysis_version_ref,
        ).where(
            HandoverActionItemRow.action_item_id == command.action_item_id,
            HandoverActionItemRow.project_id == command.project_id,
        ).with_for_update(of=HandoverActionItemRow)).one_or_none()
        if row is None or actor_role != "PROJECT_MANAGER":
            raise HandoverActionCloseError("RESOURCE_NOT_FOUND")
        action, analysis_id = row
        if action.lock_version != command.expected_version:
            raise HandoverActionCloseError("CONFLICT_VERSION")
        if action.action_state != "VERIFIED":
            raise HandoverActionCloseError("HANDOVER_ACTION_STATE_INVALID")
        if action.source_kind == "ANALYSIS_ITEM" and analysis_id is None:
            raise HandoverActionCloseError(
                "HANDOVER_ACTION_RESOLUTION_REQUIRED",
            )
        return HandoverActionCloseLock(
            action.action_item_id, action.project_id, action.lock_version,
            action.source_kind, analysis_id,
            action.source_analysis_version_ref,
        )

    def close(self, transaction: object, *, command: CloseHandoverAction,
              action: HandoverActionCloseLock, actor_id: uuid.UUID,
              occurred_at: datetime) -> HandoverActionCloseView:
        session = _session(transaction)
        event_id, version = uuid.UUID(new_uuid7()), action.lock_version + 1
        session.execute(insert(HandoverActionStateEventRow).values(
            action_state_event_id=event_id,
            action_item_id=action.action_item_id, project_id=action.project_id,
            sequence_no=version, from_state="VERIFIED", to_state="CLOSED",
            actor_id=actor_id, reason=command.reason, occurred_at=occurred_at,
            trace_id=command.trace_id,
        ))
        changed = session.execute(update(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == action.action_item_id,
            HandoverActionItemRow.project_id == action.project_id,
            HandoverActionItemRow.lock_version == action.lock_version,
            HandoverActionItemRow.action_state == "VERIFIED",
        ).values(
            action_state="CLOSED", closed_at=occurred_at,
            resolution_trace_ref=command.resolution_trace_ref,
            updated_by=actor_id, updated_at=occurred_at, lock_version=version,
        ))
        if changed.rowcount != 1:
            raise HandoverActionCloseError("CONFLICT_VERSION")
        return HandoverActionCloseView(
            action.action_item_id, action.project_id, event_id, "CLOSED",
            command.resolution_trace_ref, occurred_at, f'"v{version}"',
        )

    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID,
               actor_role: str) -> HandoverActionCloseView | None:
        session = _session(transaction)
        row = session.execute(select(
            HandoverActionItemRow.resolution_trace_ref,
            HandoverActionStateEventRow.sequence_no,
            HandoverActionStateEventRow.occurred_at,
        ).join(
            HandoverActionStateEventRow,
            (HandoverActionStateEventRow.action_item_id
             == HandoverActionItemRow.action_item_id)
            & (HandoverActionStateEventRow.project_id
               == HandoverActionItemRow.project_id),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionStateEventRow.action_state_event_id == event_id,
            HandoverActionStateEventRow.from_state == "VERIFIED",
            HandoverActionStateEventRow.to_state == "CLOSED",
            HandoverActionStateEventRow.actor_id == actor_id,
        ).with_for_update(of=HandoverActionItemRow, read=True)).one_or_none()
        if (row is None or actor_role != "PROJECT_MANAGER"
                or type(row.resolution_trace_ref) is not uuid.UUID):
            raise HandoverActionCloseError("RESOURCE_NOT_FOUND")
        return HandoverActionCloseView(
            action_item_id, project_id, event_id, "CLOSED",
            row.resolution_trace_ref, row.occurred_at,
            f'"v{row.sequence_no}"',
        )
