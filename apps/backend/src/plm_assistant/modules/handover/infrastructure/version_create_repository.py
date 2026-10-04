"""Handover-owned immutable AnalysisVersion aggregate persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, insert, select, text, update

from plm_assistant.modules.handover.application.create_version import (
    CreatedHandoverVersion, HandoverAnalysisItemDraft, HandoverAnalysisLock,
    HandoverVersionCreateError,
)
from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import (
    HandoverAITaskRefRow, HandoverAnalysisItemRow, HandoverAnalysisRow,
    HandoverAnalysisVersionRow, HandoverItemCapabilityRefRow,
    HandoverItemEvidenceRefRow, HandoverItemOptionRow,
    HandoverSourceDocumentRefRow,
)


class SqlAlchemyHandoverVersionCreateRepository:
    def lock_analysis(self, transaction: object, *, project_id: uuid.UUID,
                      handover_analysis_id: uuid.UUID) -> HandoverAnalysisLock | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(handover_analysis_id) is not uuid.UUID
                or handover_analysis_id.int == 0):
            return None
        session = _session(transaction)
        row = session.execute(select(HandoverAnalysisRow).where(
            HandoverAnalysisRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisRow.project_id == project_id,
        ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        latest = session.execute(select(
            HandoverAnalysisVersionRow.handover_analysis_version_id,
            HandoverAnalysisVersionRow.version_no,
        ).where(
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisVersionRow.project_id == project_id,
        ).order_by(HandoverAnalysisVersionRow.version_no.desc()).limit(1)
          .execution_options(autoflush=False)).one_or_none()
        return HandoverAnalysisLock(
            row.handover_analysis_id, row.project_id, row.analysis_state,
            row.source_set_ref, row.lock_version,
            0 if latest is None else latest.version_no,
            None if latest is None else latest.handover_analysis_version_id,
        )

    def create(self, transaction: object, *, analysis: HandoverAnalysisLock,
               handover_analysis_version_id: uuid.UUID,
               capability_baseline_id: uuid.UUID,
               capability_baseline_version_id: uuid.UUID,
               source_documents: tuple[HandoverDocumentRef, ...],
               items: tuple[HandoverAnalysisItemDraft, ...],
               ai_task_refs: tuple[uuid.UUID, ...], content_fingerprint: bytes,
               actor_id: uuid.UUID) -> CreatedHandoverVersion:
        if (type(analysis) is not HandoverAnalysisLock
                or type(handover_analysis_version_id) is not uuid.UUID
                or handover_analysis_version_id.int == 0
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    capability_baseline_id, capability_baseline_version_id, actor_id))
                or type(source_documents) is not tuple or not source_documents
                or any(type(item) is not HandoverDocumentRef for item in source_documents)
                or type(items) is not tuple or not items
                or any(type(item) is not HandoverAnalysisItemDraft for item in items)
                or type(ai_task_refs) is not tuple
                or type(content_fingerprint) is not bytes
                or len(content_fingerprint) != 32):
            raise HandoverVersionCreateError("VALIDATION_FAILED")
        session = _session(transaction)
        changed = session.execute(update(HandoverAnalysisRow).where(
            HandoverAnalysisRow.handover_analysis_id == analysis.handover_analysis_id,
            HandoverAnalysisRow.project_id == analysis.project_id,
            HandoverAnalysisRow.analysis_state == "ACTIVE",
            HandoverAnalysisRow.source_set_ref == analysis.source_set_ref,
            HandoverAnalysisRow.current_approved_version_ref.is_(None),
            HandoverAnalysisRow.lock_version == analysis.lock_version,
            ~exists(select(1).where(
                HandoverAnalysisVersionRow.handover_analysis_id
                == analysis.handover_analysis_id,
                HandoverAnalysisVersionRow.version_state == "IN_REVIEW",
            )),
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=HandoverAnalysisRow.lock_version + 1,
        ).returning(HandoverAnalysisRow.lock_version)).scalar_one_or_none()
        if changed != analysis.lock_version + 1:
            raise HandoverVersionCreateError("CONFLICT_VERSION")
        evidence_count = sum(len(item.evidence_refs) for item in items)
        capability_count = sum(len(item.capability_refs) for item in items)
        session.execute(insert(HandoverAnalysisVersionRow).values(
            handover_analysis_version_id=handover_analysis_version_id,
            handover_analysis_id=analysis.handover_analysis_id,
            project_id=analysis.project_id,
            version_no=analysis.highest_version_no + 1,
            version_state="DRAFT", source_set_ref=analysis.source_set_ref,
            capability_baseline_id=capability_baseline_id,
            capability_baseline_version_ref=capability_baseline_version_id,
            content_fingerprint=content_fingerprint,
            declared_source_count=len(source_documents),
            declared_item_count=len(items),
            declared_evidence_count=evidence_count,
            declared_capability_ref_count=capability_count,
            declared_ai_task_count=len(ai_task_refs),
            supersedes_version_ref=analysis.latest_version_id,
            review_ref=None, review_round_ref=None, created_by=actor_id,
        ))
        for ordinal, ref in enumerate(source_documents):
            session.execute(insert(HandoverSourceDocumentRefRow).values(
                source_document_ref_id=uuid.UUID(new_uuid7()),
                handover_analysis_version_id=handover_analysis_version_id,
                handover_analysis_id=analysis.handover_analysis_id,
                project_id=analysis.project_id, document_id=ref.document_id,
                document_version_id=ref.document_version_id, ordinal=ordinal,
            ))
        for ordinal, task_id in enumerate(ai_task_refs):
            session.execute(insert(HandoverAITaskRefRow).values(
                ai_task_ref_id=uuid.UUID(new_uuid7()),
                handover_analysis_version_id=handover_analysis_version_id,
                handover_analysis_id=analysis.handover_analysis_id,
                project_id=analysis.project_id, ai_task_id=task_id,
                task_scope="PROJECT", ordinal=ordinal,
            ))
        for item_ordinal, item in enumerate(items):
            item_row_id = uuid.UUID(new_uuid7())
            session.execute(insert(HandoverAnalysisItemRow).values(
                analysis_item_row_id=item_row_id,
                handover_analysis_version_id=handover_analysis_version_id,
                handover_analysis_id=analysis.handover_analysis_id,
                project_id=analysis.project_id,
                analysis_item_id=item.analysis_item_id, ordinal=item_ordinal,
                item_type=item.item_type, title=item.title,
                statement=item.statement, impact=item.impact,
                severity=item.severity, priority=item.priority,
                recommendation=item.recommendation,
                confirmation_question=item.confirmation_question,
                required_input_spec=item.required_input_spec,
                source_missing=item.source_missing, item_state="CANDIDATE",
            ))
            for ordinal, evidence_id in enumerate(item.evidence_refs):
                session.execute(insert(HandoverItemEvidenceRefRow).values(
                    item_evidence_ref_id=uuid.UUID(new_uuid7()),
                    analysis_item_row_id=item_row_id,
                    handover_analysis_version_id=handover_analysis_version_id,
                    handover_analysis_id=analysis.handover_analysis_id,
                    project_id=analysis.project_id, evidence_id=evidence_id,
                    ordinal=ordinal,
                ))
            for ordinal, reference in enumerate(item.capability_refs):
                session.execute(insert(HandoverItemCapabilityRefRow).values(
                    item_capability_ref_id=uuid.UUID(new_uuid7()),
                    analysis_item_row_id=item_row_id,
                    handover_analysis_version_id=handover_analysis_version_id,
                    handover_analysis_id=analysis.handover_analysis_id,
                    project_id=analysis.project_id,
                    baseline_version_id=capability_baseline_version_id,
                    capability_item_id=reference.capability_item_id,
                    ordinal=ordinal,
                ))
            for ordinal, option in enumerate(item.options):
                session.execute(insert(HandoverItemOptionRow).values(
                    item_option_id=uuid.UUID(new_uuid7()),
                    analysis_item_row_id=item_row_id,
                    handover_analysis_version_id=handover_analysis_version_id,
                    handover_analysis_id=analysis.handover_analysis_id,
                    project_id=analysis.project_id,
                    option_code=option.option_code, label=option.label,
                    description=option.description, ordinal=ordinal,
                ))
        row = session.execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == handover_analysis_version_id,
        )).scalar_one()
        return CreatedHandoverVersion(
            row.handover_analysis_version_id, row.handover_analysis_id,
            row.project_id, row.version_no, row.version_state,
            row.source_set_ref, row.capability_baseline_id,
            row.capability_baseline_version_ref, bytes(row.content_fingerprint),
            row.supersedes_version_ref, row.created_by, row.created_at,
            analysis.lock_version, analysis.lock_version + 1,
        )

    def initial_view(self, transaction: object, *,
                     handover_analysis_version_id: uuid.UUID,
                     handover_analysis_id: uuid.UUID, project_id: uuid.UUID,
                     actor_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedHandoverVersion | None:
        values = (handover_analysis_version_id, handover_analysis_id, project_id, actor_id)
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in values)
                or type(expected_lock_version) is not int or expected_lock_version < 0):
            return None
        row = _session(transaction).execute(select(HandoverAnalysisVersionRow).where(
            HandoverAnalysisVersionRow.handover_analysis_version_id
            == handover_analysis_version_id,
            HandoverAnalysisVersionRow.handover_analysis_id == handover_analysis_id,
            HandoverAnalysisVersionRow.project_id == project_id,
            HandoverAnalysisVersionRow.created_by == actor_id,
            HandoverAnalysisVersionRow.version_state == "DRAFT",
            HandoverAnalysisVersionRow.review_ref.is_(None),
            HandoverAnalysisVersionRow.review_round_ref.is_(None),
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        return CreatedHandoverVersion(
            row.handover_analysis_version_id, row.handover_analysis_id,
            row.project_id, row.version_no, row.version_state,
            row.source_set_ref, row.capability_baseline_id,
            row.capability_baseline_version_ref, bytes(row.content_fingerprint),
            row.supersedes_version_ref, row.created_by, row.created_at,
            expected_lock_version, expected_lock_version + 1,
        )
