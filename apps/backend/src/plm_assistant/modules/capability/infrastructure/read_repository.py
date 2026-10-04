"""Capability-owned read projections with database-enforced visibility predicates."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselineView, CapabilityItemView, CapabilityVersionView,
)
from .orm import (
    CapabilityBaselineRow, CapabilityBaselineVersionRow,
    CapabilityItemDocumentRefRow, CapabilityItemEvidenceRefRow, CapabilityItemRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Capability transaction is required")
    return session


def _visibility(value: str) -> None:
    if value not in {"ADMIN_HISTORY", "CURRENT_APPROVED"}:
        raise ValueError("invalid Capability visibility")


def _baseline_view(row: CapabilityBaselineRow) -> CapabilityBaselineView:
    return CapabilityBaselineView(
        row.baseline_id, row.baseline_code, row.name, row.description,
        row.baseline_state, row.source_collection_ref,
        row.current_approved_version_ref, row.created_at, row.updated_at,
        f'"v{row.lock_version}"',
    )


def _version_view(row: CapabilityBaselineVersionRow) -> CapabilityVersionView:
    return CapabilityVersionView(
        row.baseline_version_id, row.baseline_id, row.version_no,
        row.version_state, row.source_collection_ref,
        bytes(row.content_fingerprint).hex(), row.declared_item_count,
        row.declared_document_ref_count, row.declared_evidence_ref_count,
        row.supersedes_version_ref, row.review_ref, row.review_round_ref,
        row.created_at,
    )


class SqlAlchemyCapabilityReadRepository:
    @staticmethod
    def _baselines(visibility: str):
        query = select(CapabilityBaselineRow)
        if visibility == "CURRENT_APPROVED":
            query = query.where(
                CapabilityBaselineRow.baseline_state == "ACTIVE",
                CapabilityBaselineRow.current_approved_version_ref.is_not(None),
            )
        return query

    @staticmethod
    def _versions(visibility: str, baseline_id: uuid.UUID):
        query = select(CapabilityBaselineVersionRow).join(
            CapabilityBaselineRow,
            CapabilityBaselineRow.baseline_id == CapabilityBaselineVersionRow.baseline_id,
        ).where(CapabilityBaselineVersionRow.baseline_id == baseline_id)
        if visibility == "CURRENT_APPROVED":
            query = query.where(
                CapabilityBaselineRow.baseline_state == "ACTIVE",
                CapabilityBaselineRow.current_approved_version_ref
                == CapabilityBaselineVersionRow.baseline_version_id,
                CapabilityBaselineVersionRow.version_state == "APPROVED",
            )
        return query

    def list_baselines(self, transaction: object, *, visibility: str,
                       after_id: uuid.UUID | None,
                       limit: int) -> tuple[CapabilityBaselineView, ...]:
        _visibility(visibility)
        query = self._baselines(visibility)
        if after_id is not None:
            query = query.where(CapabilityBaselineRow.baseline_id > after_id)
        rows = _session(transaction).execute(query.order_by(
            CapabilityBaselineRow.baseline_id,
        ).limit(limit)).scalars().all()
        return tuple(_baseline_view(row) for row in rows)

    def get_baseline(self, transaction: object, *, visibility: str,
                     baseline_id: uuid.UUID) -> CapabilityBaselineView | None:
        _visibility(visibility)
        row = _session(transaction).execute(self._baselines(visibility).where(
            CapabilityBaselineRow.baseline_id == baseline_id,
        )).scalar_one_or_none()
        return None if row is None else _baseline_view(row)

    def list_versions(self, transaction: object, *, visibility: str,
                      baseline_id: uuid.UUID, after_version_no: int | None,
                      limit: int) -> tuple[CapabilityVersionView, ...]:
        _visibility(visibility)
        query = self._versions(visibility, baseline_id)
        if after_version_no is not None:
            query = query.where(CapabilityBaselineVersionRow.version_no < after_version_no)
        rows = _session(transaction).execute(query.order_by(
            CapabilityBaselineVersionRow.version_no.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_version_view(row) for row in rows)

    def get_version(self, transaction: object, *, visibility: str,
                    baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> CapabilityVersionView | None:
        _visibility(visibility)
        row = _session(transaction).execute(self._versions(
            visibility, baseline_id,
        ).where(
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
        )).scalar_one_or_none()
        return None if row is None else _version_view(row)

    def list_items(self, transaction: object, *, visibility: str,
                   baseline_id: uuid.UUID, baseline_version_id: uuid.UUID,
                   after_ordinal: int | None,
                   limit: int) -> tuple[CapabilityItemView, ...]:
        _visibility(visibility)
        allowed = self._versions(visibility, baseline_id).where(
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
        ).exists()
        query = select(CapabilityItemRow).where(
            CapabilityItemRow.baseline_id == baseline_id,
            CapabilityItemRow.baseline_version_id == baseline_version_id,
            allowed,
        )
        if after_ordinal is not None:
            query = query.where(CapabilityItemRow.ordinal > after_ordinal)
        session = _session(transaction)
        rows = session.execute(query.order_by(CapabilityItemRow.ordinal).limit(limit)).scalars().all()
        views: list[CapabilityItemView] = []
        for row in rows:
            documents = tuple(session.execute(select(
                CapabilityItemDocumentRefRow.document_version_id,
            ).where(
                CapabilityItemDocumentRefRow.capability_item_row_id
                == row.capability_item_row_id,
            ).order_by(CapabilityItemDocumentRefRow.ordinal)).scalars())
            evidence = tuple(session.execute(select(
                CapabilityItemEvidenceRefRow.evidence_id,
            ).where(
                CapabilityItemEvidenceRefRow.capability_item_row_id
                == row.capability_item_row_id,
            ).order_by(CapabilityItemEvidenceRefRow.ordinal)).scalars())
            views.append(CapabilityItemView(
                row.capability_item_id, row.baseline_version_id, row.baseline_id,
                row.ordinal, row.capability_code, row.domain_name, row.module_name,
                row.feature_name, row.name, row.description, row.boundary_text,
                tuple(row.prerequisites), tuple(row.interface_refs), row.item_state,
                documents, evidence,
            ))
        return tuple(views)
