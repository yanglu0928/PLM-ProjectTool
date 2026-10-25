"""Locked reconstruction of one immutable Capability Version aggregate."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.capability.application.create_version import CapabilityItemDraft
from plm_assistant.modules.capability.application.source_validation import CapabilityDocumentRef
from plm_assistant.modules.capability.application.validate_version import CapabilityVersionSnapshot

from .baseline_create_repository import _session
from .orm import (
    CapabilityBaselineVersionRow, CapabilityItemDocumentRefRow,
    CapabilityItemEvidenceRefRow, CapabilityItemRow,
)


class SqlAlchemyCapabilityVersionValidationRepository:
    def lock_snapshot(self, transaction: object, *, baseline_id: uuid.UUID,
                      baseline_version_id: uuid.UUID) -> CapabilityVersionSnapshot | None:
        if (type(baseline_id) is not uuid.UUID or baseline_id.int == 0
                or type(baseline_version_id) is not uuid.UUID
                or baseline_version_id.int == 0):
            return None
        session = _session(transaction)
        version = session.execute(select(CapabilityBaselineVersionRow).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
        ).with_for_update(read=True).execution_options(populate_existing=True)).scalar_one_or_none()
        if version is None:
            return None
        rows = session.execute(select(CapabilityItemRow).where(
            CapabilityItemRow.baseline_id == baseline_id,
            CapabilityItemRow.baseline_version_id == baseline_version_id,
        ).order_by(CapabilityItemRow.ordinal).with_for_update(read=True)
          .execution_options(populate_existing=True)).scalars().all()
        items: list[CapabilityItemDraft] = []
        for row in rows:
            documents = session.execute(select(CapabilityItemDocumentRefRow).where(
                CapabilityItemDocumentRefRow.capability_item_row_id
                == row.capability_item_row_id,
            ).order_by(CapabilityItemDocumentRefRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            evidence = session.execute(select(CapabilityItemEvidenceRefRow).where(
                CapabilityItemEvidenceRefRow.capability_item_row_id
                == row.capability_item_row_id,
            ).order_by(CapabilityItemEvidenceRefRow.ordinal).with_for_update(read=True)
              .execution_options(populate_existing=True)).scalars().all()
            items.append(CapabilityItemDraft(
                row.capability_item_id, row.capability_code, row.domain_name,
                row.module_name, row.feature_name, row.name, row.description,
                row.boundary_text, tuple(row.prerequisites), tuple(row.interface_refs),
                row.item_state, tuple(CapabilityDocumentRef(
                    item.document_id, item.document_version_id,
                ) for item in documents), tuple(item.evidence_id for item in evidence),
            ))
        if (len(items) != version.declared_item_count
                or sum(len(item.document_refs) for item in items)
                   != version.declared_document_ref_count
                or sum(len(item.evidence_refs) for item in items)
                   != version.declared_evidence_ref_count):
            return None
        return CapabilityVersionSnapshot(
            version.baseline_id, version.baseline_version_id, version.version_no,
            version.version_state, version.source_collection_ref,
            bytes(version.content_fingerprint), tuple(items),
        )
