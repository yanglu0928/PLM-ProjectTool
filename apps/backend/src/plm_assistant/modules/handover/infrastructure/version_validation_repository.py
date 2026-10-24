"""Locked reconstruction of one immutable Handover AnalysisVersion."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import select

from plm_assistant.modules.handover.application.create_version import (
    HandoverAnalysisItemDraft, HandoverCapabilityItemRef, HandoverItemOptionDraft,
)
from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.handover.application.validate_version import HandoverVersionSnapshot

from .analysis_create_repository import _session
from .orm import (
    HandoverAITaskRefRow, HandoverAnalysisItemRow, HandoverAnalysisVersionRow,
    HandoverItemCapabilityRefRow, HandoverItemEvidenceRefRow,
    HandoverItemOptionRow, HandoverSourceDocumentRefRow,
)


class SqlAlchemyHandoverVersionValidationRepository:
    def lock_snapshot(self, transaction: object, *, project_id: uuid.UUID,
                      handover_analysis_id: uuid.UUID,
                      handover_analysis_version_id: uuid.UUID
                      ) -> HandoverVersionSnapshot | None:
        values = (project_id, handover_analysis_id, handover_analysis_version_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        session = _session(transaction)
        version = session.execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == handover_analysis_version_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if version is None:
            return None
        source_rows = session.execute(select(HandoverSourceDocumentRefRow).where(
            HandoverSourceDocumentRefRow.handover_analysis_version_id
            == handover_analysis_version_id,
        ).order_by(HandoverSourceDocumentRefRow.ordinal).with_for_update(read=True)
          .execution_options(populate_existing=True)).scalars().all()
        ai_rows = session.execute(select(HandoverAITaskRefRow).where(
            HandoverAITaskRefRow.handover_analysis_version_id
            == handover_analysis_version_id,
        ).order_by(HandoverAITaskRefRow.ordinal).with_for_update(read=True)
          .execution_options(populate_existing=True)).scalars().all()
        item_rows = session.execute(select(HandoverAnalysisItemRow).where(
            HandoverAnalysisItemRow.handover_analysis_version_id
            == handover_analysis_version_id,
        ).order_by(HandoverAnalysisItemRow.ordinal).with_for_update(read=True)
          .execution_options(populate_existing=True)).scalars().all()
        items: list[HandoverAnalysisItemDraft] = []
        for row in item_rows:
            evidence = session.execute(select(HandoverItemEvidenceRefRow).where(
                HandoverItemEvidenceRefRow.analysis_item_row_id == row.analysis_item_row_id,
            ).order_by(HandoverItemEvidenceRefRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            capabilities = session.execute(select(HandoverItemCapabilityRefRow).where(
                HandoverItemCapabilityRefRow.analysis_item_row_id == row.analysis_item_row_id,
            ).order_by(HandoverItemCapabilityRefRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            options = session.execute(select(HandoverItemOptionRow).where(
                HandoverItemOptionRow.analysis_item_row_id == row.analysis_item_row_id,
            ).order_by(HandoverItemOptionRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            items.append(HandoverAnalysisItemDraft(
                row.analysis_item_id, row.item_type, row.title, row.statement,
                row.impact, row.severity, row.priority, row.recommendation,
                row.confirmation_question, copy.deepcopy(row.required_input_spec),
                row.source_missing, tuple(item.evidence_id for item in evidence),
                tuple(HandoverCapabilityItemRef(item.capability_item_id)
                      for item in capabilities),
                tuple(HandoverItemOptionDraft(
                    item.option_code, item.label, item.description,
                ) for item in options),
            ))
        evidence_count = sum(len(item.evidence_refs) for item in items)
        capability_count = sum(len(item.capability_refs) for item in items)
        if (len(source_rows) != version.declared_source_count
                or len(items) != version.declared_item_count
                or evidence_count != version.declared_evidence_count
                or capability_count != version.declared_capability_ref_count
                or len(ai_rows) != version.declared_ai_task_count):
            return None
        return HandoverVersionSnapshot(
            version.handover_analysis_id, version.handover_analysis_version_id,
            version.project_id, version.version_no, version.version_state,
            version.source_set_ref, version.capability_baseline_id,
            version.capability_baseline_version_ref,
            bytes(version.content_fingerprint),
            tuple(HandoverDocumentRef(row.document_id, row.document_version_id)
                  for row in source_rows), tuple(items),
            tuple(row.ai_task_id for row in ai_rows),
        )
