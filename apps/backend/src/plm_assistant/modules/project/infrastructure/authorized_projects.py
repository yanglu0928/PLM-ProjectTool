"""Current ProjectMember facts for an already validated User identity."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.public import ProjectAccessSummary
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberRow, ProjectRow,
)


class SqlAlchemyAuthorizedProjects:
    def for_user(self, transaction: object, user_id: uuid.UUID) -> tuple[ProjectAccessSummary, ...]:
        if type(user_id) is not uuid.UUID or user_id.int == 0:
            raise ValueError("valid user identity is required")
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project transaction is required")
        rows = session.execute(select(
            ProjectRow.project_id, ProjectRow.name, ProjectMemberRow.project_role,
        ).join(
            ProjectMemberRow,
            ProjectMemberRow.project_id == ProjectRow.project_id,
        ).join(
            DepartmentRow,
            (DepartmentRow.department_id == ProjectMemberRow.department_id)
            & (DepartmentRow.project_id == ProjectMemberRow.project_id),
        ).where(
            ProjectMemberRow.user_id == user_id,
            ProjectMemberRow.state == "ACTIVE",
            ProjectMemberRow.effective_at <= func.statement_timestamp(),
            ProjectMemberRow.ended_at.is_(None),
            ProjectRow.state == "ACTIVE",
            DepartmentRow.state == "ACTIVE",
        ).limit(2)).all()
        if len(rows) > 1:
            raise RuntimeError("ambiguous active Project membership")
        return tuple(ProjectAccessSummary(row.project_id, row.name, row.project_role)
                     for row in rows)
