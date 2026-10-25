"""Capability-owned historical/public Survey source resolver."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.capability.application.survey_source_location import (
    CapabilityDocumentLocation, CapabilitySurveySourceLocation,
)

from .orm import (
    CapabilityBaselineRow, CapabilityBaselineVersionRow,
    CapabilityItemDocumentRefRow, CapabilityItemEvidenceRefRow,
    CapabilityItemRow,
)
from .read_repository import _session


class SqlAlchemyCapabilitySurveySourceLocation:
    def resolve(
        self, transaction: object, *, capability_item_row_id: uuid.UUID,
        baseline_version_id: uuid.UUID, baseline_id: uuid.UUID,
    ) -> CapabilitySurveySourceLocation | None:
        values = (capability_item_row_id, baseline_version_id, baseline_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        session = _session(transaction)
        row = session.execute(select(
            CapabilityItemRow.capability_item_id,
            CapabilityItemRow.item_state,
            CapabilityBaselineVersionRow.version_state,
            CapabilityBaselineRow.baseline_state,
            CapabilityBaselineRow.current_approved_version_ref,
        ).join(
            CapabilityBaselineVersionRow,
            CapabilityBaselineVersionRow.baseline_version_id
            == CapabilityItemRow.baseline_version_id,
        ).join(
            CapabilityBaselineRow,
            CapabilityBaselineRow.baseline_id
            == CapabilityBaselineVersionRow.baseline_id,
        ).where(
            CapabilityItemRow.capability_item_row_id == capability_item_row_id,
            CapabilityItemRow.baseline_version_id == baseline_version_id,
            CapabilityItemRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineRow.baseline_id == baseline_id,
        ).with_for_update(read=True)).one_or_none()
        if row is None:
            return None
        documents = tuple(CapabilityDocumentLocation(*value) for value in
            session.execute(select(
                CapabilityItemDocumentRefRow.document_id,
                CapabilityItemDocumentRefRow.document_version_id,
            ).where(
                CapabilityItemDocumentRefRow.capability_item_row_id
                == capability_item_row_id,
                CapabilityItemDocumentRefRow.baseline_version_id
                == baseline_version_id,
                CapabilityItemDocumentRefRow.baseline_id == baseline_id,
            ).order_by(CapabilityItemDocumentRefRow.ordinal)))
        evidence = tuple(session.execute(select(
            CapabilityItemEvidenceRefRow.evidence_id,
        ).where(
            CapabilityItemEvidenceRefRow.capability_item_row_id
            == capability_item_row_id,
            CapabilityItemEvidenceRefRow.baseline_version_id == baseline_version_id,
            CapabilityItemEvidenceRefRow.baseline_id == baseline_id,
        ).order_by(CapabilityItemEvidenceRefRow.ordinal)).scalars())
        current = (
            row.version_state == "APPROVED"
            and row.baseline_state == "ACTIVE"
            and row.current_approved_version_ref == baseline_version_id
            and row.item_state == "AVAILABLE"
        )
        return CapabilitySurveySourceLocation(
            baseline_id, baseline_version_id, row.capability_item_id,
            row.item_state, current, documents, evidence,
        )

