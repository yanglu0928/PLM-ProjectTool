"""Handover-owned Analysis, Version, and Item read projections."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAITaskView, HandoverAnalysisItemView, HandoverAnalysisVersionView,
    HandoverAnalysisView, HandoverItemCapabilityView, HandoverItemOptionView,
    HandoverSourceDocumentView,
)

from .analysis_create_repository import _session
from .orm import (
    HandoverAITaskRefRow, HandoverAnalysisItemRow, HandoverAnalysisRow,
    HandoverAnalysisVersionRow, HandoverItemCapabilityRefRow,
    HandoverItemEvidenceRefRow, HandoverItemOptionRow,
    HandoverSourceDocumentRefRow,
)


def _analysis(row: HandoverAnalysisRow) -> HandoverAnalysisView:
    return HandoverAnalysisView(
        row.handover_analysis_id, row.project_id, row.analysis_purpose,
        row.source_set_ref, row.analysis_state, row.current_approved_version_ref,
        row.created_by, row.created_at, row.updated_at, f'"v{row.lock_version}"',
    )


def _version(row: HandoverAnalysisVersionRow, *,
             documents: tuple[HandoverSourceDocumentView, ...] = (),
             tasks: tuple[HandoverAITaskView, ...] = (),
             ) -> HandoverAnalysisVersionView:
    return HandoverAnalysisVersionView(
        row.handover_analysis_version_id, row.handover_analysis_id,
        row.project_id, row.version_no, row.version_state, row.source_set_ref,
        row.capability_baseline_id, row.capability_baseline_version_ref,
        bytes(row.content_fingerprint).hex(), row.declared_source_count,
        row.declared_item_count, row.declared_evidence_count,
        row.declared_capability_ref_count, row.declared_ai_task_count,
        row.supersedes_version_ref, row.review_ref, row.review_round_ref,
        row.created_by, row.created_at, documents, tasks,
    )


class SqlAlchemyHandoverAnalysisReadRepository:
    def list_analyses(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_handover_analysis_id: uuid.UUID | None, limit: int,
    ) -> tuple[HandoverAnalysisView, ...]:
        query = select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.project_id == project_id,
        )
        if after_updated_at is not None and after_handover_analysis_id is not None:
            query = query.where(or_(
                HandoverAnalysisRow.updated_at < after_updated_at,
                and_(HandoverAnalysisRow.updated_at == after_updated_at,
                     HandoverAnalysisRow.handover_analysis_id
                     < after_handover_analysis_id),
            ))
        rows = _session(transaction).execute(query.order_by(
            HandoverAnalysisRow.updated_at.desc(),
            HandoverAnalysisRow.handover_analysis_id.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_analysis(row) for row in rows)

    def get_analysis(self, transaction: object, *, project_id: uuid.UUID,
                     handover_analysis_id: uuid.UUID) -> HandoverAnalysisView | None:
        row = _session(transaction).execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.project_id == project_id,
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
        )).scalar_one_or_none()
        return None if row is None else _analysis(row)

    def list_versions(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID, after_version_no: int | None,
        limit: int,
    ) -> tuple[HandoverAnalysisVersionView, ...]:
        query = select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
        )
        if after_version_no is not None:
            query = query.where(
                HandoverAnalysisVersionRow.version_no < after_version_no,
            )
        rows = _session(transaction).execute(query.order_by(
            HandoverAnalysisVersionRow.version_no.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_version(row) for row in rows)

    def get_version(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
    ) -> HandoverAnalysisVersionView | None:
        session = _session(transaction)
        row = session.execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == handover_analysis_version_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        documents = tuple(HandoverSourceDocumentView(*item) for item in session.execute(
            select(
                HandoverSourceDocumentRefRow.document_id,
                HandoverSourceDocumentRefRow.document_version_id,
                HandoverSourceDocumentRefRow.ordinal,
            ).where(
                HandoverSourceDocumentRefRow.project_id == project_id,
                HandoverSourceDocumentRefRow.handover_analysis_version_id
                == handover_analysis_version_id,
            ).order_by(HandoverSourceDocumentRefRow.ordinal),
        ).all())
        tasks = tuple(HandoverAITaskView(item.ai_task_id, item.ordinal)
                      for item in session.execute(select(HandoverAITaskRefRow).where(
                          HandoverAITaskRefRow.project_id == project_id,
                          HandoverAITaskRefRow.handover_analysis_version_id
                          == handover_analysis_version_id,
                      ).order_by(HandoverAITaskRefRow.ordinal)).scalars())
        return _version(row, documents=documents, tasks=tasks)

    def list_items(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID, after_ordinal: int | None,
        limit: int,
    ) -> tuple[HandoverAnalysisItemView, ...]:
        allowed = select(HandoverAnalysisVersionRow.handover_analysis_version_id).where(
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == handover_analysis_version_id,
        ).exists()
        query = select(HandoverAnalysisItemRow).where(
            HandoverAnalysisItemRow.project_id == project_id,
            HandoverAnalysisItemRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisItemRow.handover_analysis_version_id
            == handover_analysis_version_id,
            allowed,
        )
        if after_ordinal is not None:
            query = query.where(HandoverAnalysisItemRow.ordinal > after_ordinal)
        session = _session(transaction)
        rows = session.execute(query.order_by(
            HandoverAnalysisItemRow.ordinal,
        ).limit(limit)).scalars().all()
        if not rows:
            return ()
        row_ids = tuple(row.analysis_item_row_id for row in rows)
        evidence: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for row_id, evidence_id in session.execute(select(
            HandoverItemEvidenceRefRow.analysis_item_row_id,
            HandoverItemEvidenceRefRow.evidence_id,
        ).where(
            HandoverItemEvidenceRefRow.analysis_item_row_id.in_(row_ids),
        ).order_by(
            HandoverItemEvidenceRefRow.analysis_item_row_id,
            HandoverItemEvidenceRefRow.ordinal,
        )):
            evidence[row_id].append(evidence_id)
        capabilities: dict[uuid.UUID, list[HandoverItemCapabilityView]] = defaultdict(list)
        for row_id, baseline_version_id, capability_item_id, ordinal in session.execute(select(
            HandoverItemCapabilityRefRow.analysis_item_row_id,
            HandoverItemCapabilityRefRow.baseline_version_id,
            HandoverItemCapabilityRefRow.capability_item_id,
            HandoverItemCapabilityRefRow.ordinal,
        ).where(
            HandoverItemCapabilityRefRow.analysis_item_row_id.in_(row_ids),
        ).order_by(
            HandoverItemCapabilityRefRow.analysis_item_row_id,
            HandoverItemCapabilityRefRow.ordinal,
        )):
            capabilities[row_id].append(HandoverItemCapabilityView(
                baseline_version_id, capability_item_id, ordinal,
            ))
        options: dict[uuid.UUID, list[HandoverItemOptionView]] = defaultdict(list)
        for row_id, code, label, description, ordinal in session.execute(select(
            HandoverItemOptionRow.analysis_item_row_id,
            HandoverItemOptionRow.option_code, HandoverItemOptionRow.label,
            HandoverItemOptionRow.description, HandoverItemOptionRow.ordinal,
        ).where(
            HandoverItemOptionRow.analysis_item_row_id.in_(row_ids),
        ).order_by(
            HandoverItemOptionRow.analysis_item_row_id,
            HandoverItemOptionRow.ordinal,
        )):
            options[row_id].append(HandoverItemOptionView(
                code, label, description, ordinal,
            ))
        return tuple(HandoverAnalysisItemView(
            row.analysis_item_id, row.handover_analysis_version_id,
            row.handover_analysis_id, row.project_id, row.ordinal,
            row.item_type, row.title, row.statement, row.impact, row.severity,
            row.priority, row.recommendation, row.confirmation_question,
            dict(row.required_input_spec), row.source_missing, row.item_state,
            tuple(evidence[row.analysis_item_row_id]),
            tuple(capabilities[row.analysis_item_row_id]),
            tuple(options[row.analysis_item_row_id]),
        ) for row in rows)
