"""Plan identity and immutable first response inside the caller transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.plan.application.create_plan import PlanInitialView
from .orm import PlanCreateResultRow, PlanRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Plan transaction required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Plan transaction required")
    return session


class SqlAlchemyPlanCreateRepository:
    def create(self, transaction: object, *, plan_id: uuid.UUID,
               project_id: uuid.UUID, name: str, actor_id: uuid.UUID) -> PlanInitialView:
        session = _session(transaction)
        created_at = session.execute(insert(PlanRow).values(
            plan_id=plan_id, project_id=project_id, name=name,
            plan_state="ACTIVE", current_approved_version_ref=None,
            created_by=actor_id, lock_version=0,
        ).returning(PlanRow.created_at)).scalar_one()
        session.execute(insert(PlanCreateResultRow).values(
            plan_id=plan_id, project_id=project_id, name=name, created_at=created_at,
        ))
        return PlanInitialView(plan_id, project_id, name, created_at)

    def first_result(self, transaction: object, *, plan_id: uuid.UUID,
                     project_id: uuid.UUID) -> PlanInitialView | None:
        row = _session(transaction).execute(select(PlanCreateResultRow).where(
            PlanCreateResultRow.plan_id == plan_id,
            PlanCreateResultRow.project_id == project_id,
        )).scalar_one_or_none()
        return None if row is None else PlanInitialView(
            row.plan_id, row.project_id, row.name, row.created_at)
