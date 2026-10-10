"""Project-owned member insert with Department and uniqueness checks."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.create_member import ProjectMemberCreateError
from plm_assistant.modules.project.application.read_members import MemberFacts, ProjectMemberView
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberCreateResultRow, ProjectMemberRow,
)


class SqlAlchemyProjectMemberCreateRepository:
    def save_create_result(self, transaction: object, *, project_id: uuid.UUID,
                           view: ProjectMemberView) -> None:
        transaction.session.execute(insert(ProjectMemberCreateResultRow).values(
            member_id=view.member_id, project_id=project_id, user_id=view.user_id,
            user_display_name=view.user_display_name, role=view.role,
            department_id=view.department_id, department_name=view.department_name,
            effective_at=view.effective_at,
        ))

    def get_create_result(self, transaction: object, *, project_id: uuid.UUID,
                          member_id: uuid.UUID) -> ProjectMemberView | None:
        row = transaction.session.execute(select(ProjectMemberCreateResultRow).where(
            ProjectMemberCreateResultRow.project_id == project_id,
            ProjectMemberCreateResultRow.member_id == member_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        return ProjectMemberView(
            row.member_id, row.user_id, row.user_display_name, row.role,
            row.department_id, row.department_name, "ACTIVE", row.effective_at,
            None, '"v0"',
        )

    def create(self, transaction: object, *, project_id: uuid.UUID,
               user_id: uuid.UUID, role: str, department_id: uuid.UUID,
               effective_at: datetime | None) -> MemberFacts:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project member transaction is required")
        department_name = session.execute(select(DepartmentRow.name).where(
            DepartmentRow.department_id == department_id,
            DepartmentRow.project_id == project_id,
            DepartmentRow.state == "ACTIVE",
        ).with_for_update(of=DepartmentRow)).scalar_one_or_none()
        if department_name is None:
            raise ProjectMemberCreateError("PROJECT_ROLE_INVALID")
        current = session.execute(select(ProjectMemberRow.project_member_id).where(
            ProjectMemberRow.user_id == user_id,
            ProjectMemberRow.state != "REMOVED",
        )).scalar_one_or_none()
        if current is not None:
            raise ProjectMemberCreateError("PROJECT_USER_ALREADY_ASSIGNED")
        values = dict(project_id=project_id, user_id=user_id,
                      department_id=department_id, project_role=role)
        if effective_at is not None:
            values["effective_at"] = effective_at
        row = session.execute(insert(ProjectMemberRow).values(**values).returning(
            ProjectMemberRow.project_member_id, ProjectMemberRow.project_id,
            ProjectMemberRow.user_id, ProjectMemberRow.project_role,
            ProjectMemberRow.department_id, ProjectMemberRow.state,
            ProjectMemberRow.effective_at, ProjectMemberRow.ended_at,
            ProjectMemberRow.lock_version,
        )).one()
        return MemberFacts(
            row.project_member_id, row.project_id, row.user_id, row.project_role,
            row.department_id, department_name, row.state,
            row.effective_at, row.ended_at, row.lock_version,
        )
