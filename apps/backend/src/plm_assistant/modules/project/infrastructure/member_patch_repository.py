"""Project-owned versioned assignment change and same-transaction history."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.patch_member import ProjectMemberPatchError
from plm_assistant.modules.project.application.read_members import MemberFacts
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberAssignmentHistoryRow, ProjectMemberRow,
)


class SqlAlchemyProjectMemberPatchRepository:
    def patch(self, transaction: object, *, project_id: uuid.UUID, member_id: uuid.UUID,
              expected_version: int, role: str | None, department_id: uuid.UUID | None,
              actor_user_id: uuid.UUID, trace_id: uuid.UUID) -> tuple[MemberFacts, bool]:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project member transaction is required")
        member = session.execute(select(ProjectMemberRow).where(
            ProjectMemberRow.project_member_id == member_id,
            ProjectMemberRow.project_id == project_id,
        ).with_for_update(of=ProjectMemberRow)).scalar_one_or_none()
        if member is None:
            raise ProjectMemberPatchError("RESOURCE_NOT_FOUND")
        if member.state == "REMOVED":
            raise ProjectMemberPatchError("PROJECT_ROLE_INVALID")
        if member.lock_version != expected_version:
            raise ProjectMemberPatchError("CONFLICT_VERSION")
        new_role = member.project_role if role is None else role
        new_department_id = member.department_id if department_id is None else department_id
        department_name = session.execute(select(DepartmentRow.name).where(
            DepartmentRow.department_id == new_department_id,
            DepartmentRow.project_id == project_id,
            DepartmentRow.state == "ACTIVE",
        ).with_for_update(of=DepartmentRow)).scalar_one_or_none()
        if department_name is None:
            raise ProjectMemberPatchError("PROJECT_ROLE_INVALID")
        changed = new_role != member.project_role or new_department_id != member.department_id
        if changed:
            if member.project_role == "PROJECT_MANAGER" and new_role != "PROJECT_MANAGER" and member.state == "ACTIVE":
                other_managers = session.execute(select(ProjectMemberRow.project_member_id).join(
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
                if other_managers is None:
                    raise ProjectMemberPatchError("PROJECT_ROLE_INVALID")
            before_role, before_department_id, before_version = (
                member.project_role, member.department_id, member.lock_version,
            )
            session.execute(update(ProjectMemberRow).where(
                ProjectMemberRow.project_member_id == member_id,
                ProjectMemberRow.project_id == project_id,
                ProjectMemberRow.lock_version == before_version,
            ).values(
                project_role=new_role, department_id=new_department_id,
                lock_version=ProjectMemberRow.lock_version + 1,
                updated_at=func.statement_timestamp(),
            ))
            session.execute(insert(ProjectMemberAssignmentHistoryRow).values(
                project_member_id=member_id, project_id=project_id,
                before_role=before_role, after_role=new_role,
                before_department_id=before_department_id,
                after_department_id=new_department_id,
                actor_user_id=actor_user_id, trace_id=trace_id,
                before_version=before_version, after_version=before_version + 1,
            ))
            version = before_version + 1
        else:
            version = member.lock_version
        return MemberFacts(
            member_id, project_id, member.user_id, new_role,
            new_department_id, department_name, member.state,
            member.effective_at, member.ended_at, version,
        ), changed
