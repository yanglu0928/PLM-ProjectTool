"""Project-owned proof that a user currently belongs to an active Project."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from .orm import DepartmentRow, ProjectMemberRow, ProjectRow


class SqlAlchemyCapabilityReadMembership:
    def has_active_membership(self, transaction: object, *, user_id: uuid.UUID) -> bool:
        if type(user_id) is not uuid.UUID or user_id.int == 0:
            return False
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project transaction is required")
        predicate = exists(select(ProjectMemberRow.project_member_id).join(
            ProjectRow, ProjectRow.project_id == ProjectMemberRow.project_id,
        ).join(
            DepartmentRow,
            (DepartmentRow.department_id == ProjectMemberRow.department_id)
            & (DepartmentRow.project_id == ProjectMemberRow.project_id),
        ).where(
            ProjectMemberRow.user_id == user_id,
            ProjectMemberRow.state == "ACTIVE",
            ProjectMemberRow.effective_at <= func.statement_timestamp(),
            ProjectMemberRow.ended_at.is_(None),
            DepartmentRow.state == "ACTIVE",
            ProjectRow.state == "ACTIVE",
        ))
        return bool(session.execute(select(predicate)).scalar_one())
