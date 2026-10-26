"""Bounded SQL read of immutable PlanVersion summaries."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.plan.application.list_plan_versions import (
    PlanVersionListPage, PlanVersionSummary,
)
from plm_assistant.modules.plan.infrastructure.create_repository import _session
from plm_assistant.modules.plan.infrastructure.orm import PlanRow, PlanVersionRow


class SqlAlchemyPlanVersionListRepository:
    def list_current(self, transaction: object, *, project_id: uuid.UUID,
                     plan_id: uuid.UUID, after_version_no: int | None,
                     limit: int) -> PlanVersionListPage | None:
        if (any(type(value) is not uuid.UUID or value.int == 0
                for value in (project_id, plan_id))
                or (after_version_no is not None and (
                    type(after_version_no) is not int or after_version_no < 1))
                or type(limit) is not int or not 1 <= limit <= 200):
            raise ValueError("invalid PlanVersion list query")
        session = _session(transaction)
        plan_exists = session.execute(select(PlanRow.plan_id).where(
            PlanRow.plan_id == plan_id, PlanRow.project_id == project_id,
        ).with_for_update(read=True, of=PlanRow)).scalar_one_or_none()
        if plan_exists is None:
            return None
        statement = select(PlanVersionRow).where(
            PlanVersionRow.project_id == project_id,
            PlanVersionRow.plan_id == plan_id,
        )
        if after_version_no is not None:
            statement = statement.where(PlanVersionRow.version_no < after_version_no)
        rows = tuple(session.execute(statement.order_by(
            PlanVersionRow.version_no.desc()).limit(limit + 1)).scalars())
        has_more = len(rows) > limit
        items = tuple(PlanVersionSummary(
            plan_version_id=row.plan_version_id, plan_id=row.plan_id,
            project_id=row.project_id, version_no=row.version_no,
            version_state=row.version_state,
            supersedes_version_ref=row.supersedes_version_ref,
            review_ref=row.review_ref, review_round_ref=row.review_round_ref,
            created_by=row.created_by, created_at=row.created_at,
        ) for row in rows[:limit])
        return PlanVersionListPage(
            items, items[-1].version_no if has_more and items else None, has_more)
