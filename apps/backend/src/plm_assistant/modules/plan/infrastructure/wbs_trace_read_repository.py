"""Plan-owned fixed WBS lookup for the read-only Trace proof Port."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.plan.application.read_wbs_for_trace import PlanWbsTraceIdentity
from .create_repository import _session
from .orm import PlanRow, PlanVersionRow, PlanWbsItemRow


class SqlAlchemyPlanWbsTraceReadRepository:
    def get_fixed(self, transaction: object, *, project_id: uuid.UUID,
                  wbs_item_id: uuid.UUID,
                  plan_version_id: uuid.UUID) -> PlanWbsTraceIdentity | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
                project_id, wbs_item_id, plan_version_id)):
            return None
        row = _session(transaction).execute(
            select(PlanWbsItemRow, PlanVersionRow, PlanRow)
            .join(PlanVersionRow,
                  (PlanWbsItemRow.plan_version_id == PlanVersionRow.plan_version_id)
                  & (PlanWbsItemRow.plan_id == PlanVersionRow.plan_id)
                  & (PlanWbsItemRow.project_id == PlanVersionRow.project_id))
            .join(PlanRow,
                  (PlanVersionRow.plan_id == PlanRow.plan_id)
                  & (PlanVersionRow.project_id == PlanRow.project_id))
            .where(PlanWbsItemRow.wbs_item_id == wbs_item_id,
                   PlanWbsItemRow.plan_version_id == plan_version_id,
                   PlanWbsItemRow.project_id == project_id)
            .with_for_update(read=True, of=(PlanWbsItemRow, PlanVersionRow, PlanRow))
        ).one_or_none()
        if row is None:
            return None
        item, version, plan = row
        return PlanWbsTraceIdentity(
            item.wbs_item_id, version.plan_version_id, plan.plan_id,
            plan.project_id, version.version_state, plan.plan_state)
