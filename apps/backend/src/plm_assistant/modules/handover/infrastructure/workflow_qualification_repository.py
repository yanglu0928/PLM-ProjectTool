"""PostgreSQL current-fact locks for Handover Workflow qualification."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.handover.application.source_validation import (
    HandoverDocumentRef,
)
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowActionLock, HandoverWorkflowQualificationLock,
    HandoverWorkflowQualificationOwnerError,
)

from .analysis_create_repository import _session
from .orm import (
    HandoverActionEvidenceRefRow, HandoverActionItemRow,
    HandoverActionResponseRefRow, HandoverActionStateEventRow,
    HandoverAnalysisItemRow, HandoverAnalysisRow, HandoverAnalysisVersionRow,
)
from .version_validation_repository import (
    SqlAlchemyHandoverVersionValidationRepository,
)


class SqlAlchemyHandoverWorkflowQualificationRepository:
    def __init__(self) -> None:
        self._versions = SqlAlchemyHandoverVersionValidationRepository()

    def lock_current(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
    ) -> HandoverWorkflowQualificationLock | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(handover_analysis_id) is not uuid.UUID
                or handover_analysis_id.int == 0):
            return None
        session = _session(transaction)
        analysis = session.execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if (analysis is None
                or analysis.current_approved_version_ref is None):
            return None
        version = session.execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id
            == handover_analysis_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == analysis.current_approved_version_ref,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if (version is None or version.review_ref is None
                or version.review_round_ref is None):
            return None
        snapshot = self._versions.lock_snapshot(
            transaction, project_id=project_id,
            handover_analysis_id=handover_analysis_id,
            handover_analysis_version_id=analysis.current_approved_version_ref,
        )
        if snapshot is None:
            return None
        item_states = tuple(session.execute(select(
            HandoverAnalysisItemRow.analysis_item_id,
            HandoverAnalysisItemRow.item_state,
        ).where(
            HandoverAnalysisItemRow.handover_analysis_version_id
            == snapshot.handover_analysis_version_id,
            HandoverAnalysisItemRow.handover_analysis_id
            == handover_analysis_id,
            HandoverAnalysisItemRow.project_id == project_id,
        ).order_by(HandoverAnalysisItemRow.ordinal).with_for_update(
            read=True,
        ).execution_options(populate_existing=True)).all())
        action_rows = session.execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.project_id == project_id,
            HandoverActionItemRow.source_kind == "ANALYSIS_ITEM",
            HandoverActionItemRow.source_analysis_version_ref
            == snapshot.handover_analysis_version_id,
        ).order_by(HandoverActionItemRow.action_item_id).with_for_update(
            read=True,
        ).execution_options(populate_existing=True)).scalars().all()
        actions = tuple(self._action(session, row) for row in action_rows)
        try:
            return HandoverWorkflowQualificationLock(
                snapshot, analysis.analysis_state, analysis.lock_version,
                analysis.current_approved_version_ref, version.review_ref,
                version.review_round_ref, item_states, actions,
            )
        except HandoverWorkflowQualificationOwnerError:
            raise
        except Exception:
            raise HandoverWorkflowQualificationOwnerError() from None

    @staticmethod
    def _action(session, row: HandoverActionItemRow) -> HandoverWorkflowActionLock:
        responses = session.execute(select(
            HandoverActionResponseRefRow.document_id,
            HandoverActionResponseRefRow.document_version_id,
        ).where(
            HandoverActionResponseRefRow.action_item_id == row.action_item_id,
            HandoverActionResponseRefRow.project_id == row.project_id,
        ).order_by(HandoverActionResponseRefRow.ordinal).with_for_update(
            read=True,
        ).execution_options(populate_existing=True)).all()
        evidence = session.execute(select(
            HandoverActionEvidenceRefRow.evidence_id,
            HandoverActionEvidenceRefRow.purpose,
        ).where(
            HandoverActionEvidenceRefRow.action_item_id == row.action_item_id,
            HandoverActionEvidenceRefRow.project_id == row.project_id,
        ).order_by(HandoverActionEvidenceRefRow.ordinal).with_for_update(
            read=True,
        ).execution_options(populate_existing=True)).all()
        event = session.execute(select(HandoverActionStateEventRow).where(
            HandoverActionStateEventRow.action_item_id == row.action_item_id,
            HandoverActionStateEventRow.project_id == row.project_id,
            HandoverActionStateEventRow.sequence_no == row.lock_version,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if (event is None or event.to_state != row.action_state
                or row.source_analysis_version_ref is None
                or row.source_item_id is None):
            raise HandoverWorkflowQualificationOwnerError()
        return HandoverWorkflowActionLock(
            row.action_item_id, row.project_id,
            row.source_analysis_version_ref, row.source_item_id,
            row.action_state, row.lock_version,
            tuple(HandoverDocumentRef(*value) for value in responses),
            tuple(value.evidence_id for value in evidence
                  if value.purpose == "SUBMISSION"),
            tuple(value.evidence_id for value in evidence
                  if value.purpose == "VERIFICATION"),
            row.resolution_trace_ref,
        )
