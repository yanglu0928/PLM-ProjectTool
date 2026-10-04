"""Project-owned keyset read of member history and Department display name."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.read_members import MemberFacts
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow, ProjectMemberRow


class SqlAlchemyProjectMemberReadRepository:
    def list_page(self, transaction: object, *, project_id: uuid.UUID,
                  after_member_id: uuid.UUID | None, limit: int) -> tuple[MemberFacts, ...]:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project member transaction is required")
        statement = select(
            ProjectMemberRow.project_member_id, ProjectMemberRow.project_id,
            ProjectMemberRow.user_id, ProjectMemberRow.project_role,
            ProjectMemberRow.department_id, DepartmentRow.name.label("department_name"),
            ProjectMemberRow.state, ProjectMemberRow.effective_at,
            ProjectMemberRow.ended_at, ProjectMemberRow.lock_version,
        ).join(
            DepartmentRow,
            (DepartmentRow.department_id == ProjectMemberRow.department_id)
            & (DepartmentRow.project_id == ProjectMemberRow.project_id),
        ).where(ProjectMemberRow.project_id == project_id)
        if after_member_id is not None:
            statement = statement.where(ProjectMemberRow.project_member_id > after_member_id)
        rows = session.execute(statement.order_by(
            ProjectMemberRow.project_member_id,
        ).limit(limit)).all()
        return tuple(MemberFacts(
            row.project_member_id, row.project_id, row.user_id, row.project_role,
            row.department_id, row.department_name, row.state,
            row.effective_at, row.ended_at, row.lock_version,
        ) for row in rows)
