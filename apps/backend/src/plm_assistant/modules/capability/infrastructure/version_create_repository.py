"""Capability-owned immutable Version aggregate persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, insert, select, text, update

from plm_assistant.modules.capability.application.create_version import (
    CapabilityBaselineLock, CapabilityItemDraft,
    CapabilityVersionCreateError, CreatedCapabilityVersion,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .baseline_create_repository import _session
from .orm import (
    CapabilityBaselineRow, CapabilityBaselineVersionRow,
    CapabilityItemDocumentRefRow, CapabilityItemEvidenceRefRow,
    CapabilityItemRow,
)


class SqlAlchemyCapabilityVersionCreateRepository:
    def lock_baseline(self, transaction: object, *,
                      baseline_id: uuid.UUID) -> CapabilityBaselineLock | None:
        if type(baseline_id) is not uuid.UUID or baseline_id.int == 0:
            return None
        session = _session(transaction)
        row = session.execute(select(CapabilityBaselineRow).where(
            CapabilityBaselineRow.baseline_id == baseline_id,
        ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        latest = session.execute(select(
            CapabilityBaselineVersionRow.baseline_version_id,
            CapabilityBaselineVersionRow.version_no,
        ).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
        ).order_by(
            CapabilityBaselineVersionRow.version_no.desc(),
        ).limit(1).execution_options(autoflush=False)).one_or_none()
        return CapabilityBaselineLock(
            row.baseline_id, row.baseline_state, row.source_collection_ref,
            row.lock_version, 0 if latest is None else latest.version_no,
            None if latest is None else latest.baseline_version_id,
        )

    def create(self, transaction: object, *, baseline: CapabilityBaselineLock,
               baseline_version_id: uuid.UUID, items: tuple[CapabilityItemDraft, ...],
               content_fingerprint: bytes,
               actor_id: uuid.UUID) -> CreatedCapabilityVersion:
        if (type(baseline) is not CapabilityBaselineLock
                or type(baseline_version_id) is not uuid.UUID
                or baseline_version_id.int == 0
                or type(items) is not tuple or not items
                or any(type(item) is not CapabilityItemDraft for item in items)
                or type(content_fingerprint) is not bytes
                or len(content_fingerprint) != 32
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            raise CapabilityVersionCreateError("VALIDATION_FAILED")
        session = _session(transaction)
        changed = session.execute(update(CapabilityBaselineRow).where(
            CapabilityBaselineRow.baseline_id == baseline.baseline_id,
            CapabilityBaselineRow.baseline_state == "ACTIVE",
            CapabilityBaselineRow.source_collection_ref == baseline.source_collection_ref,
            CapabilityBaselineRow.current_approved_version_ref.is_(None),
            CapabilityBaselineRow.lock_version == baseline.lock_version,
            ~exists(select(1).where(
                CapabilityBaselineVersionRow.baseline_id == baseline.baseline_id,
                CapabilityBaselineVersionRow.version_state == "IN_REVIEW",
            )),
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=CapabilityBaselineRow.lock_version + 1,
        ).returning(CapabilityBaselineRow.lock_version)).scalar_one_or_none()
        if changed != baseline.lock_version + 1:
            raise CapabilityVersionCreateError("CONFLICT_VERSION")
        version_no = baseline.highest_version_no + 1
        document_count = sum(len(item.document_refs) for item in items)
        evidence_count = sum(len(item.evidence_refs) for item in items)
        session.execute(insert(CapabilityBaselineVersionRow).values(
            baseline_version_id=baseline_version_id,
            baseline_id=baseline.baseline_id, version_no=version_no,
            version_state="DRAFT",
            source_collection_ref=baseline.source_collection_ref,
            content_fingerprint=content_fingerprint,
            declared_item_count=len(items),
            declared_document_ref_count=document_count,
            declared_evidence_ref_count=evidence_count,
            supersedes_version_ref=baseline.latest_version_id,
            review_ref=None, review_round_ref=None, created_by=actor_id,
        ))
        for item_ordinal, item in enumerate(items):
            item_row_id = uuid.UUID(new_uuid7())
            session.execute(insert(CapabilityItemRow).values(
                capability_item_row_id=item_row_id,
                baseline_version_id=baseline_version_id,
                baseline_id=baseline.baseline_id,
                capability_item_id=item.capability_item_id,
                ordinal=item_ordinal, capability_code=item.capability_code,
                domain_name=item.domain_name, module_name=item.module_name,
                feature_name=item.feature_name, name=item.name,
                description=item.description, boundary_text=item.boundary_text,
                prerequisites=list(item.prerequisites),
                interface_refs=list(item.interface_refs), item_state=item.item_state,
            ))
            for ordinal, reference in enumerate(item.document_refs):
                session.execute(insert(CapabilityItemDocumentRefRow).values(
                    capability_item_document_ref_id=uuid.UUID(new_uuid7()),
                    capability_item_row_id=item_row_id,
                    baseline_version_id=baseline_version_id,
                    baseline_id=baseline.baseline_id,
                    document_id=reference.document_id,
                    document_version_id=reference.document_version_id,
                    ordinal=ordinal,
                ))
            for ordinal, evidence_id in enumerate(item.evidence_refs):
                session.execute(insert(CapabilityItemEvidenceRefRow).values(
                    capability_item_evidence_ref_id=uuid.UUID(new_uuid7()),
                    capability_item_row_id=item_row_id,
                    baseline_version_id=baseline_version_id,
                    baseline_id=baseline.baseline_id,
                    evidence_id=evidence_id, ordinal=ordinal,
                ))
        row = session.execute(select(CapabilityBaselineVersionRow).where(
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
        )).scalar_one()
        return CreatedCapabilityVersion(
            row.baseline_version_id, row.baseline_id, row.version_no,
            row.version_state, row.source_collection_ref,
            bytes(row.content_fingerprint), row.supersedes_version_ref,
            row.created_by, row.created_at,
            baseline.lock_version, baseline.lock_version + 1,
        )

    def initial_view(self, transaction: object, *, baseline_version_id: uuid.UUID,
                     baseline_id: uuid.UUID, actor_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedCapabilityVersion | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                baseline_version_id, baseline_id, actor_id))
                or type(expected_lock_version) is not int
                or expected_lock_version < 0):
            return None
        row = _session(transaction).execute(select(
            CapabilityBaselineVersionRow,
        ).where(
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.created_by == actor_id,
            CapabilityBaselineVersionRow.version_state == "DRAFT",
            CapabilityBaselineVersionRow.review_ref.is_(None),
            CapabilityBaselineVersionRow.review_round_ref.is_(None),
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        return CreatedCapabilityVersion(
            row.baseline_version_id, row.baseline_id, row.version_no,
            row.version_state, row.source_collection_ref,
            bytes(row.content_fingerprint), row.supersedes_version_ref,
            row.created_by, row.created_at,
            expected_lock_version, expected_lock_version + 1,
        )
