"""Project-owned Department insert with active-code conflict handling."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plm_assistant.modules.project.application.read_departments import DepartmentFacts
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow


class SqlAlchemyProjectDepartmentCreateRepository:
    def create(self, transaction: object, *, project_id: uuid.UUID,
               code: str, normalized_code: str, name: str) -> DepartmentFacts | None:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project Department transaction is required")
        row = session.execute(pg_insert(DepartmentRow).values(
            project_id=project_id, department_code=code,
            department_code_normalized=normalized_code, name=name,
        ).on_conflict_do_nothing(
            index_elements=(DepartmentRow.project_id, DepartmentRow.department_code_normalized),
            index_where=DepartmentRow.state == "ACTIVE",
        ).returning(
            DepartmentRow.department_id, DepartmentRow.project_id,
            DepartmentRow.department_code, DepartmentRow.name,
            DepartmentRow.state, DepartmentRow.created_at,
            DepartmentRow.lock_version,
        )).one_or_none()
        if row is None:
            return None
        return DepartmentFacts(
            row.department_id, row.project_id, row.department_code,
            row.name, row.state, row.created_at, row.lock_version,
        )
