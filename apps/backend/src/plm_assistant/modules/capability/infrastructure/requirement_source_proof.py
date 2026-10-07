"""Current approved GLOBAL Capability item and Review proof for Requirement."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.capability.application.requirement_source_proof import (
    CapabilityRequirementSourceProof,
)
from plm_assistant.modules.review.infrastructure.orm import (
    ReviewRow, ReviewRoundRow, ReviewSubjectSnapshotRow,
)

from .orm import CapabilityBaselineRow, CapabilityBaselineVersionRow, CapabilityItemRow
from .read_repository import _session


class SqlAlchemyCapabilityRequirementSourceProof:
    def prove(
        self, transaction: object, *, baseline_version_id: uuid.UUID,
        capability_item_id: uuid.UUID,
    ) -> CapabilityRequirementSourceProof | None:
        if any(
            type(value) is not uuid.UUID or value.int == 0
            for value in (baseline_version_id, capability_item_id)
        ):
            return None
        row = _session(transaction).execute(select(
            CapabilityBaselineVersionRow.baseline_version_id,
            CapabilityBaselineVersionRow.baseline_id,
            CapabilityItemRow.capability_item_id,
            CapabilityItemRow.capability_item_row_id,
            ReviewRow.review_id,
            ReviewRoundRow.review_round_id,
            CapabilityBaselineVersionRow.version_no,
            CapabilityBaselineVersionRow.content_fingerprint,
        ).select_from(CapabilityBaselineRow).join(
            CapabilityBaselineVersionRow,
            CapabilityBaselineVersionRow.baseline_id
            == CapabilityBaselineRow.baseline_id,
        ).join(
            CapabilityItemRow,
            (CapabilityItemRow.baseline_version_id
             == CapabilityBaselineVersionRow.baseline_version_id)
            & (CapabilityItemRow.baseline_id
               == CapabilityBaselineVersionRow.baseline_id),
        ).join(
            ReviewRow,
            ReviewRow.review_id == CapabilityBaselineVersionRow.review_ref,
        ).join(
            ReviewRoundRow,
            (ReviewRoundRow.review_round_id
             == CapabilityBaselineVersionRow.review_round_ref)
            & (ReviewRoundRow.review_id == ReviewRow.review_id),
        ).join(
            ReviewSubjectSnapshotRow,
            (ReviewSubjectSnapshotRow.review_round_id
             == ReviewRoundRow.review_round_id)
            & (ReviewSubjectSnapshotRow.review_id == ReviewRow.review_id),
        ).where(
            CapabilityBaselineVersionRow.baseline_version_id
            == baseline_version_id,
            CapabilityItemRow.capability_item_id == capability_item_id,
            CapabilityBaselineRow.baseline_state == "ACTIVE",
            CapabilityBaselineRow.current_approved_version_ref
            == baseline_version_id,
            CapabilityBaselineVersionRow.version_state == "APPROVED",
            CapabilityItemRow.item_state == "AVAILABLE",
            ReviewRow.scope == "GLOBAL",
            ReviewRow.project_id.is_(None),
            ReviewRow.subject_type == "CAP-01",
            ReviewRow.subject_id == CapabilityBaselineRow.baseline_id,
            ReviewRow.policy_code == "DEPLOYMENT_ALL_V1",
            ReviewRow.review_state == "APPROVED",
            ReviewRow.active_round_id.is_(None),
            ReviewRoundRow.scope == "GLOBAL",
            ReviewRoundRow.project_id.is_(None),
            ReviewRoundRow.subject_version_id == baseline_version_id,
            ReviewRoundRow.round_state == "APPROVED",
            ReviewSubjectSnapshotRow.scope == "GLOBAL",
            ReviewSubjectSnapshotRow.project_id.is_(None),
            ReviewSubjectSnapshotRow.subject_type == "CAP-01",
            ReviewSubjectSnapshotRow.subject_id
            == CapabilityBaselineRow.baseline_id,
            ReviewSubjectSnapshotRow.subject_version_id == baseline_version_id,
            ReviewSubjectSnapshotRow.content_fingerprint
            == CapabilityBaselineVersionRow.content_fingerprint,
            ReviewSubjectSnapshotRow.proof_schema_version == 1,
        ).with_for_update(
            read=True,
            of=(CapabilityBaselineRow, CapabilityBaselineVersionRow,
                CapabilityItemRow, ReviewRow, ReviewRoundRow,
                ReviewSubjectSnapshotRow),
        ).execution_options(populate_existing=True)).one_or_none()
        return (
            None if row is None
            else CapabilityRequirementSourceProof(*row[:-1], bytes(row[-1]))
        )
