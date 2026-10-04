"""Capability-owned Review Subject lock and DRAFT binding persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text, update

from plm_assistant.modules.capability.application.review_subject import (
    CapabilityReviewLock,
)
from plm_assistant.modules.capability.infrastructure.baseline_create_repository import (
    _session,
)
from plm_assistant.modules.capability.infrastructure.orm import (
    CapabilityBaselineRow,
    CapabilityBaselineVersionRow,
)
from plm_assistant.modules.capability.infrastructure.version_validation_repository import (
    SqlAlchemyCapabilityVersionValidationRepository,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
)


class SqlAlchemyCapabilityReviewSubjectRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemyCapabilityVersionValidationRepository()

    def lock_subject(
        self, transaction: object, *, baseline_id: uuid.UUID,
        baseline_version_id: uuid.UUID,
    ) -> CapabilityReviewLock | None:
        if (type(baseline_id) is not uuid.UUID or baseline_id.int == 0
                or type(baseline_version_id) is not uuid.UUID
                or baseline_version_id.int == 0):
            return None
        session = _session(transaction)
        baseline = session.execute(select(CapabilityBaselineRow).where(
            CapabilityBaselineRow.baseline_id == baseline_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if baseline is None:
            return None
        version = session.execute(select(CapabilityBaselineVersionRow).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
            CapabilityBaselineVersionRow.baseline_version_id
            == baseline_version_id,
        ).with_for_update().execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if version is None:
            return None
        snapshot = self._snapshots.lock_snapshot(
            transaction, baseline_id=baseline_id,
            baseline_version_id=baseline_version_id,
        )
        if snapshot is None:
            return None
        latest = session.execute(select(
            CapabilityBaselineVersionRow.baseline_version_id,
        ).where(
            CapabilityBaselineVersionRow.baseline_id == baseline_id,
        ).order_by(
            CapabilityBaselineVersionRow.version_no.desc(),
        ).limit(1)).scalar_one_or_none()
        if latest is None:
            return None
        return CapabilityReviewLock(
            snapshot, baseline.baseline_state, baseline.lock_version,
            baseline.current_approved_version_ref, latest,
            version.review_ref, version.review_round_ref,
        )

    def bind_start(
        self, transaction: object, *, before: CapabilityReviewLock,
        review_id: uuid.UUID, round_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        if (type(before) is not CapabilityReviewLock
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (review_id, round_id, actor_id))):
            raise ReviewSubjectAccessDenied()
        before.__post_init__()
        session = _session(transaction)
        version = before.snapshot
        changed = session.execute(update(
            CapabilityBaselineVersionRow,
        ).where(
            CapabilityBaselineVersionRow.baseline_id == version.baseline_id,
            CapabilityBaselineVersionRow.baseline_version_id
            == version.baseline_version_id,
            CapabilityBaselineVersionRow.version_state == "DRAFT",
            CapabilityBaselineVersionRow.review_ref.is_(None),
            CapabilityBaselineVersionRow.review_round_ref.is_(None),
        ).values(
            version_state="IN_REVIEW", review_ref=review_id,
            review_round_ref=round_id,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
        changed = session.execute(update(CapabilityBaselineRow).where(
            CapabilityBaselineRow.baseline_id == version.baseline_id,
            CapabilityBaselineRow.baseline_state == "ACTIVE",
            CapabilityBaselineRow.lock_version == before.baseline_lock_version,
        ).values(
            updated_by=actor_id, updated_at=text("statement_timestamp()"),
            lock_version=CapabilityBaselineRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise ReviewSubjectAccessDenied()
