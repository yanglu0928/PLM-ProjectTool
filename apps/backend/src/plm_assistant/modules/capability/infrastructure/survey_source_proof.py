"""Capability current-approved item proof for Survey writes."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.capability.application.survey_source_proof import (
    CapabilitySurveySourceProof,
)

from .orm import CapabilityBaselineRow, CapabilityBaselineVersionRow, CapabilityItemRow
from .read_repository import _session


class SqlAlchemyCapabilitySurveySourceProof:
    def prove(
        self, transaction: object, *, capability_item_row_id: uuid.UUID,
        baseline_version_id: uuid.UUID, baseline_id: uuid.UUID,
    ) -> CapabilitySurveySourceProof | None:
        values = (capability_item_row_id, baseline_version_id, baseline_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        row = _session(transaction).execute(select(
            CapabilityItemRow.capability_item_row_id,
            CapabilityItemRow.baseline_version_id,
            CapabilityItemRow.baseline_id,
            CapabilityItemRow.capability_item_id,
            CapabilityItemRow.item_state,
        ).join(
            CapabilityBaselineVersionRow,
            CapabilityBaselineVersionRow.baseline_version_id
            == CapabilityItemRow.baseline_version_id,
        ).join(
            CapabilityBaselineRow,
            CapabilityBaselineRow.baseline_id == CapabilityBaselineVersionRow.baseline_id,
        ).where(
            CapabilityItemRow.capability_item_row_id == capability_item_row_id,
            CapabilityItemRow.baseline_version_id == baseline_version_id,
            CapabilityItemRow.baseline_id == baseline_id,
            CapabilityItemRow.item_state == "AVAILABLE",
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.version_state == "APPROVED",
            CapabilityBaselineRow.baseline_state == "ACTIVE",
            CapabilityBaselineRow.current_approved_version_ref == baseline_version_id,
        ).with_for_update(read=True)).one_or_none()
        return None if row is None else CapabilitySurveySourceProof(*row)
