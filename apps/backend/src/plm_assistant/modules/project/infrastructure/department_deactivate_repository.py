"""Project-owned guarded Department deactivation in the authorization transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.deactivate_department import ProjectDepartmentDeactivateError
from plm_assistant.modules.project.application.read_departments import DepartmentFacts
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow, ProjectMemberRow


class SqlAlchemyProjectDepartmentDeactivateRepository:
    def deactivate(self, transaction: object, *, project_id: uuid.UUID,
                   department_id: uuid.UUID, expected_version: int) -> DepartmentFacts:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project Department transaction is required")
        department = session.execute(select(DepartmentRow).where(
            DepartmentRow.department_id == department_id,
            DepartmentRow.project_id == project_id,
        ).with_for_update(of=DepartmentRow)).scalar_one_or_none()
        if department is None:
            raise ProjectDepartmentDeactivateError("RESOURCE_NOT_FOUND")
        if department.lock_version != expected_version:
            raise ProjectDepartmentDeactivateError("CONFLICT_VERSION")
        if department.state != "ACTIVE":
            raise ProjectDepartmentDeactivateError("CONFLICT_STATE")
        active_or_suspended = session.execute(select(ProjectMemberRow.project_member_id).where(
            ProjectMemberRow.project_id == project_id,
            ProjectMemberRow.department_id == department_id,
            ProjectMemberRow.state.in_(("ACTIVE", "SUSPENDED")),
        ).limit(1)).scalar_one_or_none()
        if active_or_suspended is not None:
            raise ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_IN_USE")
        row = session.execute(update(DepartmentRow).where(
            DepartmentRow.department_id == department_id,
            DepartmentRow.project_id == project_id,
            DepartmentRow.state == "ACTIVE",
            DepartmentRow.lock_version == expected_version,
        ).values(
            state="INACTIVE", lock_version=DepartmentRow.lock_version + 1,
            updated_at=func.statement_timestamp(),
        ).returning(
            DepartmentRow.department_id, DepartmentRow.project_id,
            DepartmentRow.department_code, DepartmentRow.name,
            DepartmentRow.state, DepartmentRow.created_at,
            DepartmentRow.lock_version,
        )).one_or_none()
        if row is None:
            raise ProjectDepartmentDeactivateError("CONFLICT_VERSION")
        return DepartmentFacts(
            row.department_id, row.project_id, row.department_code,
            row.name, row.state, row.created_at, row.lock_version,
        )
