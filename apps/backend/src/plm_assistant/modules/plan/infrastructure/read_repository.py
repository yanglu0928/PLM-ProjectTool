"""Project-scoped Plan identity reads; first-result snapshots are not current state."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import select, tuple_

from plm_assistant.modules.plan.application.read_plan import (
    PlanCurrentView, PlanListPage, PlanSummaryView,
)
from .create_repository import _session
from .orm import PlanRow


class SqlAlchemyPlanReadRepository:
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    plan_id: uuid.UUID) -> PlanCurrentView | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(plan_id) is not uuid.UUID or plan_id.int == 0):
            return None
        row = _session(transaction).execute(select(PlanRow).where(
            PlanRow.plan_id == plan_id, PlanRow.project_id == project_id,
        ).with_for_update(read=True, of=PlanRow)).scalar_one_or_none()
        if row is None:
            return None
        self._require_pointer_closed(row)
        return PlanCurrentView(
            row.plan_id, row.project_id, row.name, row.plan_state,
            None, row.created_by, row.created_at, f'"v{row.lock_version}"')

    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     after_created_at: datetime | None,
                     after_plan_id: uuid.UUID | None, limit: int) -> PlanListPage:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or ((after_created_at is None) != (after_plan_id is None))
                or (after_created_at is not None and (
                    type(after_created_at) is not datetime
                    or after_created_at.tzinfo is None
                    or after_created_at.utcoffset() is None))
                or (after_plan_id is not None and (
                    type(after_plan_id) is not uuid.UUID or after_plan_id.int == 0))
                or type(limit) is not int or not 1 <= limit <= 200):
            raise ValueError("invalid Plan list query")
        statement = select(PlanRow).where(PlanRow.project_id == project_id)
        if after_created_at is not None:
            statement = statement.where(tuple_(PlanRow.created_at, PlanRow.plan_id)
                                        < tuple_(after_created_at, after_plan_id))
        rows = tuple(_session(transaction).execute(statement.order_by(
            PlanRow.created_at.desc(), PlanRow.plan_id.desc()).limit(limit + 1).with_for_update(
                read=True, of=PlanRow)).scalars().all())
        items = []
        for row in rows[:limit]:
            self._require_pointer_closed(row)
            items.append(PlanSummaryView(
                row.plan_id, row.project_id, row.name, row.plan_state,
                None, row.created_at, f'"v{row.lock_version}"'))
        has_more = len(rows) > limit
        return PlanListPage(
            tuple(items), items[-1].created_at if has_more else None,
            items[-1].plan_id if has_more else None, has_more)

    @staticmethod
    def _require_pointer_closed(row: PlanRow) -> None:
        if row.current_approved_version_ref is not None:
            raise RuntimeError("Plan approved pointer is not yet installed")
