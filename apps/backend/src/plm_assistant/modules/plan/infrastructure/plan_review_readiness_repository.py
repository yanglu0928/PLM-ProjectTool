"""Exclusive Plan identity/version locks for a Review readiness proof."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanVersionReviewLock,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import PlanRow, PlanVersionRow
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import (
    SqlAlchemyPlanVersionReadRepository,
)


class SqlAlchemyPlanVersionReviewReadinessRepository:
    """Locks the identity before versions, matching the PlanVersion create Owner."""

    def __init__(self, *, snapshots: SqlAlchemyPlanVersionReadRepository | None = None) -> None:
        self._snapshots = snapshots or SqlAlchemyPlanVersionReadRepository()

    def lock_current(self, transaction: object, *, project_id: uuid.UUID,
                     plan_id: uuid.UUID,
                     plan_version_id: uuid.UUID) -> PlanVersionReviewLock | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
                project_id, plan_id, plan_version_id)):
            return None
        session = _session(transaction)
        plan = session.execute(select(PlanRow).where(
            PlanRow.plan_id == plan_id,
            PlanRow.project_id == project_id,
        ).with_for_update(of=PlanRow).execution_options(
            populate_existing=True)).scalar_one_or_none()
        if plan is None or plan.plan_state != "ACTIVE":
            return None
        versions = tuple(session.execute(select(PlanVersionRow).where(
            PlanVersionRow.plan_id == plan_id,
            PlanVersionRow.project_id == project_id,
        ).order_by(PlanVersionRow.version_no.desc(),
                   PlanVersionRow.plan_version_id).with_for_update(
                       of=PlanVersionRow).execution_options(
                           populate_existing=True)).scalars())
        if not versions or versions[0].plan_version_id != plan_version_id:
            return None
        snapshot = self._snapshots.get_current(
            transaction, project_id=project_id, plan_id=plan_id,
            plan_version_id=plan_version_id)
        if (snapshot is None or snapshot.version_no != versions[0].version_no
                or snapshot.version_state != versions[0].version_state
                or snapshot.review_ref != versions[0].review_ref
                or snapshot.review_round_ref != versions[0].review_round_ref):
            return None
        return PlanVersionReviewLock(snapshot, versions[0].plan_version_id)
