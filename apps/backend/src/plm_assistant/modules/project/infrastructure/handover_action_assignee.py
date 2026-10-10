"""Project-owned current membership fact for Handover Action assignment."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.project.infrastructure.authorization_repository import _session
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberRow, ProjectRow,
)


class SqlAlchemyHandoverActionAssigneeSource:
    def is_current_member(
        self, transaction: object, *, project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(user_id) is not uuid.UUID or user_id.int == 0):
            return False
        found = _session(transaction).execute(select(
            ProjectMemberRow.user_id,
        ).join(
            ProjectRow, ProjectRow.project_id == ProjectMemberRow.project_id,
        ).join(
            DepartmentRow,
            (DepartmentRow.department_id == ProjectMemberRow.department_id)
            & (DepartmentRow.project_id == ProjectMemberRow.project_id),
        ).join(
            UserRow, UserRow.user_id == ProjectMemberRow.user_id,
        ).where(
            ProjectMemberRow.project_id == project_id,
            ProjectMemberRow.user_id == user_id,
            ProjectMemberRow.state == "ACTIVE",
            ProjectMemberRow.effective_at <= func.statement_timestamp(),
            ProjectMemberRow.ended_at.is_(None),
            DepartmentRow.state == "ACTIVE",
            ProjectRow.state == "ACTIVE",
            UserRow.state == "ENABLED",
        ).with_for_update(
            of=(ProjectRow, ProjectMemberRow, DepartmentRow, UserRow),
            read=True,
        )).scalar_one_or_none()
        return found == user_id
