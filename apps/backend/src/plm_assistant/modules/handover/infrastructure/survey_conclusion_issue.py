"""SQL HND-03 current-state proof owned by Handover."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.handover.application.survey_conclusion_issue import (
    SurveyConclusionIssueProof,
)

from .analysis_create_repository import _session
from .orm import HandoverActionItemRow, HandoverActionStateEventRow


class SqlAlchemySurveyConclusionIssueProof:
    def prove(self, transaction: object, *, project_id: uuid.UUID,
              action_item_id: uuid.UUID) -> SurveyConclusionIssueProof | None:
        if (transaction is None or any(
                type(value) is not uuid.UUID or value.int == 0
                for value in (project_id, action_item_id))):
            return None
        row = _session(transaction).execute(select(
            HandoverActionItemRow.action_item_id,
            HandoverActionItemRow.project_id,
            HandoverActionItemRow.action_type,
            HandoverActionItemRow.action_state,
            HandoverActionItemRow.lock_version,
            HandoverActionItemRow.updated_at,
        ).join(
            HandoverActionStateEventRow,
            (HandoverActionStateEventRow.action_item_id
             == HandoverActionItemRow.action_item_id)
            & (HandoverActionStateEventRow.project_id
               == HandoverActionItemRow.project_id)
            & (HandoverActionStateEventRow.sequence_no
               == HandoverActionItemRow.lock_version),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionStateEventRow.to_state == HandoverActionItemRow.action_state,
        ).with_for_update(
            read=True, of=(HandoverActionItemRow, HandoverActionStateEventRow),
        ).execution_options(populate_existing=True)).one_or_none()
        return None if row is None else SurveyConclusionIssueProof(*row)
