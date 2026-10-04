"""Row-locked Capability metadata/archive/restriction persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.capability.application.change_state import (
    CapabilityRestrictionMutation, CapabilityStateError,
)
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselineView, CapabilityVersionView,
)
from .orm import CapabilityBaselineRow, CapabilityBaselineVersionRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise CapabilityStateError()
    return session


def _baseline(row: CapabilityBaselineRow) -> CapabilityBaselineView:
    return CapabilityBaselineView(
        row.baseline_id, row.baseline_code, row.name, row.description,
        row.baseline_state, row.source_collection_ref,
        row.current_approved_version_ref, row.created_at, row.updated_at,
        f'"v{row.lock_version}"',
    )


def _version(row: CapabilityBaselineVersionRow) -> CapabilityVersionView:
    return CapabilityVersionView(
        row.baseline_version_id, row.baseline_id, row.version_no,
        row.version_state, row.source_collection_ref,
        bytes(row.content_fingerprint).hex(), row.declared_item_count,
        row.declared_document_ref_count, row.declared_evidence_ref_count,
        row.supersedes_version_ref, row.review_ref, row.review_round_ref,
        row.created_at,
    )


class SqlAlchemyCapabilityStateRepository:
    def get_baseline(self, transaction: object, *,
                     baseline_id: uuid.UUID) -> CapabilityBaselineView | None:
        row = _session(transaction).get(CapabilityBaselineRow, baseline_id)
        return None if row is None else _baseline(row)

    def get_version(self, transaction: object, *, baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> CapabilityVersionView | None:
        row = _session(transaction).execute(select(CapabilityBaselineVersionRow).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
        )).scalar_one_or_none()
        return None if row is None else _version(row)

    def patch(self, transaction: object, *, baseline_id: uuid.UUID,
              expected_lock_version: int, name: str, description: str | None,
              actor_id: uuid.UUID) -> CapabilityBaselineView:
        row = self._lock_baseline(transaction, baseline_id)
        self._writable(row, expected_lock_version)
        if row.name == name and row.description == description:
            raise CapabilityStateError("CONFLICT_STATE")
        row.name, row.description = name, description
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    def archive(self, transaction: object, *, baseline_id: uuid.UUID,
                expected_lock_version: int,
                actor_id: uuid.UUID) -> CapabilityBaselineView:
        session = _session(transaction)
        row = self._lock_baseline(transaction, baseline_id)
        self._writable(row, expected_lock_version)
        active_review = session.execute(select(
            CapabilityBaselineVersionRow.baseline_version_id,
        ).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.version_state == "IN_REVIEW",
        ).limit(1)).scalar_one_or_none()
        if active_review is not None:
            raise CapabilityStateError("CONFLICT_STATE")
        row.baseline_state = "ARCHIVED"
        self._advance(row, actor_id)
        return self._refresh(transaction, row)

    def restrict(self, transaction: object, *, baseline_id: uuid.UUID,
                 baseline_version_id: uuid.UUID,
                 actor_id: uuid.UUID) -> CapabilityRestrictionMutation:
        session = _session(transaction)
        baseline = self._lock_baseline(transaction, baseline_id)
        if baseline.baseline_state != "ACTIVE":
            raise CapabilityStateError("CONFLICT_STATE")
        version = session.execute(select(CapabilityBaselineVersionRow).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.baseline_version_id == baseline_version_id,
        ).with_for_update(of=CapabilityBaselineVersionRow)).scalar_one_or_none()
        if version is None:
            raise CapabilityStateError("RESOURCE_NOT_FOUND")
        if version.version_state not in {"DRAFT", "APPROVED", "RETURNED", "SUPERSEDED"}:
            raise CapabilityStateError("CONFLICT_STATE")
        if (baseline.current_approved_version_ref == baseline_version_id
                and version.version_state != "APPROVED"):
            raise CapabilityStateError()
        before_state = version.version_state
        version.version_state = "RESTRICTED"
        if baseline.current_approved_version_ref == baseline_version_id:
            baseline.current_approved_version_ref = None
        self._advance(baseline, actor_id)
        session.flush()
        session.refresh(version)
        return CapabilityRestrictionMutation(_version(version), before_state)

    @staticmethod
    def _lock_baseline(transaction: object,
                       baseline_id: uuid.UUID) -> CapabilityBaselineRow:
        row = _session(transaction).execute(select(CapabilityBaselineRow).where(
            CapabilityBaselineRow.baseline_id == baseline_id,
        ).with_for_update(of=CapabilityBaselineRow)).scalar_one_or_none()
        if row is None:
            raise CapabilityStateError("RESOURCE_NOT_FOUND")
        return row

    @staticmethod
    def _writable(row: CapabilityBaselineRow, expected: int) -> None:
        if row.lock_version != expected:
            raise CapabilityStateError("CONFLICT_VERSION")
        if row.baseline_state != "ACTIVE":
            raise CapabilityStateError("CONFLICT_STATE")

    @staticmethod
    def _advance(row: CapabilityBaselineRow, actor_id: uuid.UUID) -> None:
        row.updated_by = actor_id
        row.updated_at = func.statement_timestamp()
        row.lock_version += 1

    @staticmethod
    def _refresh(transaction: object,
                 row: CapabilityBaselineRow) -> CapabilityBaselineView:
        session = _session(transaction)
        session.flush()
        session.refresh(row)
        return _baseline(row)
