"""SolutionOutline first-response persistence inside the caller transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select

from plm_assistant.modules.solution.application.create_outline import OutlineInitialView
from .orm import SolutionOutlineCreateResultRow, SolutionOutlineRow
from .reference_deidentification_repository import _session


class SqlAlchemyOutlineCreateRepository:
    def create(self, transaction: object, *, outline_id: uuid.UUID,
               project_id: uuid.UUID, name: str, actor_id: uuid.UUID) -> OutlineInitialView:
        session = _session(transaction)
        created_at = session.execute(insert(SolutionOutlineRow).values(
            solution_outline_id=outline_id, project_id=project_id, name=name,
            outline_state="ACTIVE", current_approved_version_ref=None,
            created_by=actor_id, lock_version=0,
        ).returning(SolutionOutlineRow.created_at)).scalar_one()
        session.execute(insert(SolutionOutlineCreateResultRow).values(
            solution_outline_id=outline_id, project_id=project_id,
            name=name, created_at=created_at,
        ))
        return OutlineInitialView(outline_id, project_id, name, created_at)

    def first_result(self, transaction: object, *, outline_id: uuid.UUID,
                     project_id: uuid.UUID) -> OutlineInitialView | None:
        row = _session(transaction).execute(select(SolutionOutlineCreateResultRow).where(
            SolutionOutlineCreateResultRow.solution_outline_id == outline_id,
            SolutionOutlineCreateResultRow.project_id == project_id,
        )).scalar_one_or_none()
        return None if row is None else OutlineInitialView(
            row.solution_outline_id, row.project_id, row.name, row.created_at)
