"""Project-owned keyset read of scoped Department history."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.read_departments import DepartmentFacts
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow


class SqlAlchemyProjectDepartmentReadRepository:
    def list_page(self, transaction: object, *, project_id: uuid.UUID,
                  after_department_id: uuid.UUID | None,
                  limit: int) -> tuple[DepartmentFacts, ...]:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project Department transaction is required")
        statement = select(
            DepartmentRow.department_id, DepartmentRow.project_id,
            DepartmentRow.department_code, DepartmentRow.name,
            DepartmentRow.state, DepartmentRow.created_at,
            DepartmentRow.lock_version,
        ).where(DepartmentRow.project_id == project_id)
        if after_department_id is not None:
            statement = statement.where(DepartmentRow.department_id > after_department_id)
        rows = session.execute(statement.order_by(
            DepartmentRow.department_id,
        ).limit(limit)).all()
        return tuple(DepartmentFacts(
            row.department_id, row.project_id, row.department_code,
            row.name, row.state, row.created_at, row.lock_version,
        ) for row in rows)
