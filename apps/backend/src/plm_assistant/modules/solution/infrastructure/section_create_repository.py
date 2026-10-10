"""SolutionSection first-response persistence in the caller transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select

from plm_assistant.modules.solution.application.create_section import SectionInitialView
from .orm import SolutionOutlineRow, SolutionSectionCreateResultRow, SolutionSectionRow
from .reference_deidentification_repository import _session


class SqlAlchemySectionCreateRepository:
    def require_active_outline(self, transaction: object, *, project_id: uuid.UUID,
                               outline_id: uuid.UUID) -> bool:
        row = _session(transaction).execute(
            select(SolutionOutlineRow.solution_outline_id).where(
                SolutionOutlineRow.solution_outline_id == outline_id,
                SolutionOutlineRow.project_id == project_id,
                SolutionOutlineRow.outline_state == "ACTIVE",
            ).with_for_update()
        ).scalar_one_or_none()
        return row == outline_id

    def create(self, transaction: object, *, section_id: uuid.UUID, project_id: uuid.UUID,
               outline_id: uuid.UUID, section_key: str, actor_id: uuid.UUID) -> SectionInitialView:
        session = _session(transaction)
        created_at = session.execute(insert(SolutionSectionRow).values(
            solution_section_id=section_id, solution_outline_id=outline_id,
            project_id=project_id, section_key=section_key,
            section_state="ACTIVE", current_approved_version_ref=None,
            created_by=actor_id, lock_version=0,
        ).returning(SolutionSectionRow.created_at)).scalar_one()
        session.execute(insert(SolutionSectionCreateResultRow).values(
            solution_section_id=section_id, solution_outline_id=outline_id,
            project_id=project_id, section_key=section_key, created_at=created_at,
        ))
        return SectionInitialView(section_id, outline_id, project_id, section_key, created_at)

    def first_result(self, transaction: object, *, section_id: uuid.UUID,
                     project_id: uuid.UUID) -> SectionInitialView | None:
        row = _session(transaction).execute(select(SolutionSectionCreateResultRow).where(
            SolutionSectionCreateResultRow.solution_section_id == section_id,
            SolutionSectionCreateResultRow.project_id == project_id,
        )).scalar_one_or_none()
        return None if row is None else SectionInitialView(
            row.solution_section_id, row.solution_outline_id, row.project_id,
            row.section_key, row.created_at)
