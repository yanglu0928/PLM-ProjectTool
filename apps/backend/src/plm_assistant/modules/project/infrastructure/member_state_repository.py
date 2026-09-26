"""Project-owned conditional member state changes in an authorized transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.change_member_state import ProjectMemberStateError
from plm_assistant.modules.project.application.read_members import MemberFacts, ProjectMemberView
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberRow, ProjectMemberStateResultRow,
)


_TRANSITIONS = {
    "SUSPEND": (frozenset({"ACTIVE"}), "SUSPENDED"),
    "RESUME": (frozenset({"SUSPENDED"}), "ACTIVE"),
    "REMOVE": (frozenset({"ACTIVE", "SUSPENDED"}), "REMOVED"),
}


class SqlAlchemyProjectMemberStateRepository:
    def save_state_result(self, transaction: object, *, result_id: uuid.UUID,
                          project_id: uuid.UUID, operation: str,
                          view: ProjectMemberView, version: int) -> None:
        transaction.session.execute(insert(ProjectMemberStateResultRow).values(
            result_id=result_id, project_id=project_id, member_id=view.member_id,
            operation=operation, user_id=view.user_id,
            user_display_name=view.user_display_name, role=view.role,
            department_id=view.department_id, department_name=view.department_name,
            state=view.state, effective_at=view.effective_at,
            ended_at=view.ended_at, lock_version=version,
        ))

    def get_state_result(self, transaction: object, *, result_id: uuid.UUID,
                         project_id: uuid.UUID, member_id: uuid.UUID,
                         operation: str) -> ProjectMemberView | None:
        row = transaction.session.execute(select(ProjectMemberStateResultRow).where(
            ProjectMemberStateResultRow.result_id == result_id,
            ProjectMemberStateResultRow.project_id == project_id,
            ProjectMemberStateResultRow.member_id == member_id,
            ProjectMemberStateResultRow.operation == operation,
        )).scalar_one_or_none()
        if row is None:
            return None
        return ProjectMemberView(
            row.member_id, row.user_id, row.user_display_name, row.role,
            row.department_id, row.department_name, row.state,
            row.effective_at, row.ended_at, f'"v{row.lock_version}"',
        )

    def change(self, transaction: object, *, project_id: uuid.UUID, member_id: uuid.UUID,
               expected_version: int, operation: str) -> tuple[MemberFacts, str]:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project member transaction is required")
        allowed_states, next_state = _TRANSITIONS[operation]
        member = session.execute(select(ProjectMemberRow).where(
            ProjectMemberRow.project_member_id == member_id,
            ProjectMemberRow.project_id == project_id,
        ).with_for_update(of=ProjectMemberRow)).scalar_one_or_none()
        if member is None:
            raise ProjectMemberStateError("RESOURCE_NOT_FOUND")
        if member.lock_version != expected_version:
            raise ProjectMemberStateError("CONFLICT_VERSION")
        if member.state not in allowed_states:
            raise ProjectMemberStateError("CONFLICT_STATE")
        department = session.execute(select(DepartmentRow.name, DepartmentRow.state).where(
            DepartmentRow.department_id == member.department_id,
            DepartmentRow.project_id == project_id,
        ).with_for_update(of=DepartmentRow)).one_or_none()
        if department is None:
            raise ProjectMemberStateError("PROJECT_UNAVAILABLE")
        if operation == "RESUME" and department.state != "ACTIVE":
            raise ProjectMemberStateError("PROJECT_ROLE_INVALID")
        if (member.state == "ACTIVE" and member.project_role == "PROJECT_MANAGER"
                and operation in ("SUSPEND", "REMOVE")):
            other = session.execute(select(ProjectMemberRow.project_member_id).join(
                DepartmentRow,
                (DepartmentRow.department_id == ProjectMemberRow.department_id)
                & (DepartmentRow.project_id == ProjectMemberRow.project_id),
            ).where(
                ProjectMemberRow.project_id == project_id,
                ProjectMemberRow.project_member_id != member_id,
                ProjectMemberRow.project_role == "PROJECT_MANAGER",
                ProjectMemberRow.state == "ACTIVE",
                ProjectMemberRow.effective_at <= func.statement_timestamp(),
                ProjectMemberRow.ended_at.is_(None),
                DepartmentRow.state == "ACTIVE",
            ).limit(1)).scalar_one_or_none()
            if other is None:
                raise ProjectMemberStateError("PROJECT_ROLE_INVALID")
        old_state = member.state
        values = dict(
            state=next_state, lock_version=ProjectMemberRow.lock_version + 1,
            updated_at=func.statement_timestamp(),
        )
        if operation == "REMOVE":
            # A future-effective member may be removed before its start time.
            values["ended_at"] = func.greatest(func.statement_timestamp(), member.effective_at)
        updated = session.execute(update(ProjectMemberRow).where(
            ProjectMemberRow.project_member_id == member_id,
            ProjectMemberRow.project_id == project_id,
            ProjectMemberRow.lock_version == expected_version,
            ProjectMemberRow.state == old_state,
        ).values(**values).returning(
            ProjectMemberRow.ended_at, ProjectMemberRow.lock_version,
        )).one_or_none()
        if updated is None:
            raise ProjectMemberStateError("CONFLICT_VERSION")
        return MemberFacts(
            member_id, project_id, member.user_id, member.project_role,
            member.department_id, department.name, next_state,
            member.effective_at,
            updated.ended_at, updated.lock_version,
        ), old_state
