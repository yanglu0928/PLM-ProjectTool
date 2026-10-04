"""Capability-owned initial Baseline identity persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineInitialView,
)

from .orm import CapabilityBaselineRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Capability transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Capability transaction is required")
    return session


class SqlAlchemyCapabilityBaselineCreateRepository:
    def create(
        self, transaction: object, *, baseline_id: uuid.UUID,
        baseline_code: str, name: str, description: str | None,
        source_collection_ref: str, actor_id: uuid.UUID,
    ) -> None:
        if (type(baseline_id) is not uuid.UUID or baseline_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            raise ValueError("validated Capability identity required")
        _session(transaction).execute(insert(CapabilityBaselineRow).values(
            baseline_id=baseline_id, baseline_code=baseline_code,
            name=name, description=description, baseline_state="ACTIVE",
            source_collection_ref=source_collection_ref,
            current_approved_version_ref=None, created_by=actor_id,
            updated_by=None, lock_version=0,
        ))

    def initial_view(
        self, transaction: object, *, baseline_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> CapabilityBaselineInitialView | None:
        if (type(baseline_id) is not uuid.UUID or baseline_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            return None
        row = _session(transaction).execute(select(CapabilityBaselineRow).where(
            CapabilityBaselineRow.baseline_id == baseline_id,
            CapabilityBaselineRow.created_by == actor_id,
            CapabilityBaselineRow.baseline_state == "ACTIVE",
            CapabilityBaselineRow.current_approved_version_ref.is_(None),
            CapabilityBaselineRow.lock_version == 0,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            return None
        return CapabilityBaselineInitialView(
            row.baseline_id, row.baseline_code, row.name, row.description,
            row.source_collection_ref, row.created_at,
        )
