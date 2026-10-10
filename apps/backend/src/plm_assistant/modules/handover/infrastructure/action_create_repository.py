"""Handover-owned initial ActionItem and state-event persistence."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime

from sqlalchemy import insert, select

from plm_assistant.modules.handover.application.create_action import (
    CreateHandoverAction, HandoverActionInitialView, HandoverActionSource,
)

from .analysis_create_repository import _session
from .orm import (
    HandoverActionItemRow, HandoverActionStateEventRow,
    HandoverAnalysisItemRow, HandoverAnalysisVersionRow,
)


class SqlAlchemyHandoverActionCreateRepository:
    def lock_source(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID, analysis_item_id: uuid.UUID,
    ) -> HandoverActionSource | None:
        values = (project_id, handover_analysis_version_id, analysis_item_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        row = _session(transaction).execute(select(
            HandoverAnalysisItemRow.project_id,
            HandoverAnalysisItemRow.handover_analysis_version_id,
            HandoverAnalysisItemRow.analysis_item_id,
            HandoverAnalysisVersionRow.version_state,
            HandoverAnalysisItemRow.item_state,
        ).join(
            HandoverAnalysisVersionRow,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == HandoverAnalysisItemRow.handover_analysis_version_id,
        ).where(
            HandoverAnalysisItemRow.project_id == project_id,
            HandoverAnalysisItemRow.handover_analysis_version_id
            == handover_analysis_version_id,
            HandoverAnalysisItemRow.analysis_item_id == analysis_item_id,
        ).with_for_update(
            of=(HandoverAnalysisVersionRow, HandoverAnalysisItemRow),
            read=True,
        ).execution_options(populate_existing=True)).one_or_none()
        return None if row is None else HandoverActionSource(*row)

    def create(
        self, transaction: object, *, action_item_id: uuid.UUID,
        initial_event_id: uuid.UUID, command: CreateHandoverAction,
        actor_id: uuid.UUID, source_kind: str, occurred_at: datetime,
    ) -> None:
        session = _session(transaction)
        session.execute(insert(HandoverActionItemRow).values(
            action_item_id=action_item_id, project_id=command.project_id,
            source_kind=source_kind,
            source_analysis_version_ref=command.source_analysis_version_ref,
            source_item_id=command.source_item_id,
            human_source_reason=command.human_source_reason,
            action_type=command.action_type, title=command.title,
            requested_input_spec=copy.deepcopy(command.requested_input_spec),
            owner_ref=command.owner_ref, due_at=command.due_at,
            priority=command.priority, action_state="OPEN",
            submitted_at=None, verified_by=None, verified_at=None,
            closed_at=None, resolution_trace_ref=None,
            created_by=actor_id, created_reason=command.created_reason,
            created_at=occurred_at, updated_by=None, updated_at=occurred_at,
            lock_version=0,
        ))
        session.execute(insert(HandoverActionStateEventRow).values(
            action_state_event_id=initial_event_id,
            action_item_id=action_item_id, project_id=command.project_id,
            sequence_no=0, from_state=None, to_state="OPEN",
            actor_id=actor_id, reason=command.created_reason,
            occurred_at=occurred_at, trace_id=command.trace_id,
        ))

    def initial_view(
        self, transaction: object, *, action_item_id: uuid.UUID,
        project_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> HandoverActionInitialView | None:
        values = (action_item_id, project_id, actor_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        row = _session(transaction).execute(select(
            HandoverActionItemRow, HandoverActionStateEventRow.action_state_event_id,
        ).join(
            HandoverActionStateEventRow,
            (HandoverActionStateEventRow.action_item_id
             == HandoverActionItemRow.action_item_id)
            & (HandoverActionStateEventRow.project_id
               == HandoverActionItemRow.project_id)
            & (HandoverActionStateEventRow.sequence_no == 0),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionItemRow.created_by == actor_id,
            HandoverActionItemRow.action_state == "OPEN",
            HandoverActionItemRow.lock_version == 0,
            HandoverActionStateEventRow.from_state.is_(None),
            HandoverActionStateEventRow.to_state == "OPEN",
            HandoverActionStateEventRow.actor_id == actor_id,
            HandoverActionStateEventRow.reason
            == HandoverActionItemRow.created_reason,
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None:
            return None
        action, event_id = row
        return HandoverActionInitialView(
            action.action_item_id, action.project_id, action.source_kind,
            action.source_analysis_version_ref, action.source_item_id,
            action.human_source_reason, action.action_type, action.title,
            copy.deepcopy(action.requested_input_spec), action.owner_ref,
            action.due_at, action.priority, action.created_by,
            action.created_reason, action.created_at, event_id,
        )
