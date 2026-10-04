"""Handover-owned versioned Action metadata update."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select, update

from plm_assistant.modules.handover.application.patch_action import (
    HandoverActionPatchError, HandoverActionPatchView, PatchHandoverAction,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import HandoverActionItemRow, HandoverActionStateEventRow


class SqlAlchemyHandoverActionPatchRepository:
    def patch(self, transaction: object, *, command: PatchHandoverAction,
              actor_id: uuid.UUID, actor_role: str,
              occurred_at: datetime) -> tuple[HandoverActionPatchView, bool]:
        session = _session(transaction)
        row = session.execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == command.action_item_id,
            HandoverActionItemRow.project_id == command.project_id,
        ).with_for_update(of=HandoverActionItemRow)).scalar_one_or_none()
        if row is None:
            raise HandoverActionPatchError("RESOURCE_NOT_FOUND")
        if actor_role not in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER") \
                and row.owner_ref != actor_id:
            raise HandoverActionPatchError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise HandoverActionPatchError("CONFLICT_VERSION")
        if row.action_state not in ("OPEN", "IN_PROGRESS"):
            raise HandoverActionPatchError("HANDOVER_STATE_INVALID")
        values = {
            "title": row.title if command.title is None else command.title,
            "requested_input_spec": (copy.deepcopy(row.requested_input_spec)
                                     if command.requested_input_spec is None
                                     else copy.deepcopy(command.requested_input_spec)),
            "owner_ref": row.owner_ref if command.owner_ref is None else command.owner_ref,
            "due_at": (row.due_at if command.due_at is None
                       else command.due_at.astimezone(timezone.utc)),
            "priority": row.priority if command.priority is None else command.priority,
        }
        changed = any((
            values["title"] != row.title,
            values["requested_input_spec"] != row.requested_input_spec,
            values["owner_ref"] != row.owner_ref,
            values["due_at"] != row.due_at,
            values["priority"] != row.priority,
        ))
        version = row.lock_version
        if changed:
            version += 1
            reason = "Action metadata updated: " + ",".join(
                key for key in values if values[key] != getattr(row, key)
            )
            session.execute(insert(HandoverActionStateEventRow).values(
                action_state_event_id=uuid.UUID(new_uuid7()),
                action_item_id=row.action_item_id, project_id=row.project_id,
                sequence_no=version, from_state=row.action_state,
                to_state=row.action_state, actor_id=actor_id, reason=reason,
                occurred_at=occurred_at, trace_id=command.trace_id,
            ))
            result = session.execute(update(HandoverActionItemRow).where(
                HandoverActionItemRow.action_item_id == row.action_item_id,
                HandoverActionItemRow.project_id == row.project_id,
                HandoverActionItemRow.lock_version == row.lock_version,
            ).values(**values, updated_by=actor_id, updated_at=occurred_at,
                     lock_version=version))
            if result.rowcount != 1:
                raise HandoverActionPatchError("CONFLICT_VERSION")
        return HandoverActionPatchView(
            row.action_item_id, row.project_id, values["title"],
            copy.deepcopy(values["requested_input_spec"]), values["owner_ref"],
            values["due_at"], values["priority"], row.action_state,
            occurred_at if changed else row.updated_at, f'"v{version}"',
        ), changed
