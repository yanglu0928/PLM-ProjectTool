"""Row-locked Handover Analysis metadata and archive persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.handover.application.change_analysis import (
    HandoverAnalysisStateError,
)
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisView,
)

from .analysis_create_repository import _session
from .orm import HandoverAnalysisRow, HandoverAnalysisVersionRow


def _view(row: HandoverAnalysisRow) -> HandoverAnalysisView:
    return HandoverAnalysisView(
        row.handover_analysis_id, row.project_id, row.analysis_purpose,
        row.source_set_ref, row.analysis_state, row.current_approved_version_ref,
        row.created_by, row.created_at, row.updated_at, f'"v{row.lock_version}"',
    )


class SqlAlchemyHandoverAnalysisStateRepository:
    def get(self, transaction: object, *, project_id: uuid.UUID,
            handover_analysis_id: uuid.UUID) -> HandoverAnalysisView | None:
        row = _session(transaction).execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
        )).scalar_one_or_none()
        return None if row is None else _view(row)

    def patch(self, transaction: object, *, project_id: uuid.UUID,
              handover_analysis_id: uuid.UUID, expected_lock_version: int,
              analysis_purpose: str,
              actor_id: uuid.UUID) -> HandoverAnalysisView:
        row = self._lock(transaction, project_id, handover_analysis_id)
        self._writable(row, expected_lock_version)
        self._review_fence(transaction, project_id, handover_analysis_id)
        if row.analysis_purpose == analysis_purpose:
            raise HandoverAnalysisStateError("CONFLICT_STATE")
        row.analysis_purpose = analysis_purpose
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    def archive(self, transaction: object, *, project_id: uuid.UUID,
                handover_analysis_id: uuid.UUID, expected_lock_version: int,
                actor_id: uuid.UUID) -> HandoverAnalysisView:
        row = self._lock(transaction, project_id, handover_analysis_id)
        self._writable(row, expected_lock_version)
        self._review_fence(transaction, project_id, handover_analysis_id)
        row.analysis_state = "ARCHIVED"
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    @staticmethod
    def _lock(transaction: object, project_id: uuid.UUID,
              analysis_id: uuid.UUID) -> HandoverAnalysisRow:
        row = _session(transaction).execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == analysis_id,
        ).with_for_update(of=HandoverAnalysisRow)).scalar_one_or_none()
        if row is None:
            raise HandoverAnalysisStateError("RESOURCE_NOT_FOUND")
        return row

    @staticmethod
    def _writable(row: HandoverAnalysisRow, expected: int) -> None:
        if row.lock_version != expected:
            raise HandoverAnalysisStateError("CONFLICT_VERSION")
        if row.analysis_state != "ACTIVE":
            raise HandoverAnalysisStateError("HANDOVER_STATE_CONFLICT")

    @staticmethod
    def _review_fence(transaction: object, project_id: uuid.UUID,
                      analysis_id: uuid.UUID) -> None:
        active = _session(transaction).execute(select(
            HandoverAnalysisVersionRow.handover_analysis_version_id,
        ).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id == analysis_id,
            HandoverAnalysisVersionRow.version_state == "IN_REVIEW",
        ).with_for_update(read=True).limit(1)).scalar_one_or_none()
        if active is not None:
            raise HandoverAnalysisStateError("HANDOVER_STATE_CONFLICT")

    @staticmethod
    def _advance(row: HandoverAnalysisRow, actor_id: uuid.UUID) -> None:
        row.updated_by = actor_id
        row.updated_at = func.statement_timestamp()
        row.lock_version += 1

    @staticmethod
    def _refresh(transaction: object,
                 row: HandoverAnalysisRow) -> HandoverAnalysisView:
        session = _session(transaction)
        session.flush()
        session.refresh(row)
        return _view(row)
