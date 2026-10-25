"""Atomic Project/Department/first Manager insert in the caller transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.create_project import CreatedProject, ProjectCreateError
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow, ProjectMemberRow, ProjectRow


class SqlAlchemyProjectCreateRepository:
    def created_at(self, transaction: object, project_id: uuid.UUID) -> datetime | None:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project transaction is required")
        return session.execute(select(ProjectRow.created_at).where(
            ProjectRow.project_id == project_id,
        )).scalar_one_or_none()

    def create(self, transaction: object, *, code: str, normalized_code: str,
               name: str, department_code: str, department_normalized_code: str,
               department_name: str, manager_user_id: uuid.UUID,
               created_by: uuid.UUID) -> CreatedProject | None:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project transaction is required")
        current = session.execute(select(ProjectMemberRow.project_member_id).where(
            ProjectMemberRow.user_id == manager_user_id,
            ProjectMemberRow.state != "REMOVED",
        )).scalar_one_or_none()
        if current is not None:
            raise ProjectCreateError("PROJECT_USER_ALREADY_ASSIGNED")
        project_id = session.execute(pg_insert(ProjectRow).values(
            project_code=code, project_code_normalized=normalized_code,
            name=name, created_by=created_by,
        ).on_conflict_do_nothing(
            constraint="uq_prj_projects__code_norm",
        ).returning(ProjectRow.project_id)).scalar_one_or_none()
        if project_id is None:
            return None
        department_id = session.execute(insert(DepartmentRow).values(
            project_id=project_id, department_code=department_code,
            department_code_normalized=department_normalized_code,
            name=department_name,
        ).returning(DepartmentRow.department_id)).scalar_one()
        member_id = session.execute(insert(ProjectMemberRow).values(
            project_id=project_id, user_id=manager_user_id,
            department_id=department_id, project_role="PROJECT_MANAGER",
        ).returning(ProjectMemberRow.project_member_id)).scalar_one()
        return CreatedProject(project_id, department_id, member_id, code, name)
