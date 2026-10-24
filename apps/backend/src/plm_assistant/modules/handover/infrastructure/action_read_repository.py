"""Handover-owned Action list and detail read projections."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.handover.application.read_actions import (
    HandoverActionCurrentEventView, HandoverActionDetailView,
    HandoverActionEvidenceView, HandoverActionResponseView,
    HandoverActionSummaryView,
)

from .analysis_create_repository import _session
from .orm import (
    HandoverActionEvidenceRefRow, HandoverActionItemRow,
    HandoverActionResponseRefRow, HandoverActionStateEventRow,
)


def _summary(row: HandoverActionItemRow) -> HandoverActionSummaryView:
    return HandoverActionSummaryView(
        row.action_item_id, row.project_id, row.source_kind, row.action_type,
        row.title, row.owner_ref, row.due_at, row.priority, row.action_state,
        row.submitted_at, row.verified_at, row.closed_at,
        row.resolution_trace_ref, row.updated_at, f'"v{row.lock_version}"',
    )


class SqlAlchemyHandoverActionReadRepository:
    def list_page(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None, after_action_item_id: uuid.UUID | None,
        limit: int,
    ) -> tuple[HandoverActionSummaryView, ...]:
        query = select(HandoverActionItemRow).where(
            HandoverActionItemRow.project_id == project_id,
        )
        if after_updated_at is not None and after_action_item_id is not None:
            query = query.where(or_(
                HandoverActionItemRow.updated_at < after_updated_at,
                and_(HandoverActionItemRow.updated_at == after_updated_at,
                     HandoverActionItemRow.action_item_id < after_action_item_id),
            ))
        rows = _session(transaction).execute(query.order_by(
            HandoverActionItemRow.updated_at.desc(),
            HandoverActionItemRow.action_item_id.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_summary(row) for row in rows)

    def get(self, transaction: object, *, project_id: uuid.UUID,
            action_item_id: uuid.UUID) -> HandoverActionDetailView | None:
        session = _session(transaction)
        row = session.execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.project_id == project_id,
            HandoverActionItemRow.action_item_id == action_item_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        responses = tuple(HandoverActionResponseView(*item) for item in session.execute(
            select(
                HandoverActionResponseRefRow.document_id,
                HandoverActionResponseRefRow.document_version_id,
                HandoverActionResponseRefRow.ordinal,
            ).where(
                HandoverActionResponseRefRow.action_item_id == action_item_id,
                HandoverActionResponseRefRow.project_id == project_id,
            ).order_by(HandoverActionResponseRefRow.ordinal),
        ).all())
        evidence = tuple(HandoverActionEvidenceView(*item) for item in session.execute(
            select(
                HandoverActionEvidenceRefRow.evidence_id,
                HandoverActionEvidenceRefRow.purpose,
                HandoverActionEvidenceRefRow.ordinal,
            ).where(
                HandoverActionEvidenceRefRow.action_item_id == action_item_id,
                HandoverActionEvidenceRefRow.project_id == project_id,
            ).order_by(HandoverActionEvidenceRefRow.ordinal),
        ).all())
        event = session.execute(select(HandoverActionStateEventRow).where(
            HandoverActionStateEventRow.action_item_id == action_item_id,
            HandoverActionStateEventRow.project_id == project_id,
            HandoverActionStateEventRow.sequence_no == row.lock_version,
        )).scalar_one_or_none()
        if event is None:
            raise RuntimeError("Handover Action current event missing")
        return HandoverActionDetailView(
            _summary(row), row.source_analysis_version_ref, row.source_item_id,
            row.human_source_reason, dict(row.requested_input_spec), responses,
            evidence, row.created_by, row.created_reason, row.created_at,
            row.verified_by, HandoverActionCurrentEventView(
                event.action_state_event_id, event.sequence_no, event.from_state,
                event.to_state, event.actor_id, event.reason, event.occurred_at,
            ),
        )
