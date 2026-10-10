"""Handover-owned initial Analysis identity persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.handover.application.create_analysis import (
    HandoverAnalysisInitialView,
)

from .orm import HandoverAnalysisRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Handover transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Handover transaction is required")
    return session


class SqlAlchemyHandoverAnalysisCreateRepository:
    def create(
        self, transaction: object, *, handover_analysis_id: uuid.UUID,
        project_id: uuid.UUID, analysis_purpose: str,
        source_set_ref: str, actor_id: uuid.UUID,
    ) -> None:
        if (type(handover_analysis_id) is not uuid.UUID
                or handover_analysis_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            raise ValueError("validated Handover identity required")
        _session(transaction).execute(insert(HandoverAnalysisRow).values(
            handover_analysis_id=handover_analysis_id, project_id=project_id,
            analysis_purpose=analysis_purpose, source_set_ref=source_set_ref,
            analysis_state="ACTIVE", current_approved_version_ref=None,
            created_by=actor_id, updated_by=None, lock_version=0,
        ))

    def initial_view(
        self, transaction: object, *, handover_analysis_id: uuid.UUID,
        project_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> HandoverAnalysisInitialView | None:
        if (type(handover_analysis_id) is not uuid.UUID
                or handover_analysis_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            return None
        row = _session(transaction).execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.created_by == actor_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
            HandoverAnalysisRow.current_approved_version_ref.is_(None),
            HandoverAnalysisRow.lock_version == 0,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        return HandoverAnalysisInitialView(
            row.handover_analysis_id, row.project_id, row.analysis_purpose,
            row.source_set_ref, row.created_at,
        )
