"""Current Project membership and target ownership checks in one transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.authorization import ProjectActorFacts
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberRow, ProjectRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Project authorization transaction is required")
    return session


class SqlAlchemyProjectAuthorizationRepository:
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None:
        statement = select(
            ProjectRow.state, ProjectMemberRow.project_role,
        ).join(
            ProjectMemberRow, ProjectMemberRow.project_id == ProjectRow.project_id,
        ).join(
            DepartmentRow,
            (DepartmentRow.department_id == ProjectMemberRow.department_id)
            & (DepartmentRow.project_id == ProjectMemberRow.project_id),
        ).where(
            ProjectRow.project_id == project_id,
            ProjectMemberRow.user_id == user_id,
            ProjectMemberRow.state == "ACTIVE",
            ProjectMemberRow.effective_at <= func.statement_timestamp(),
            ProjectMemberRow.ended_at.is_(None),
            DepartmentRow.state == "ACTIVE",
        )
        if lock:
            statement = statement.with_for_update(of=(ProjectRow, ProjectMemberRow, DepartmentRow))
        row = _session(transaction).execute(statement).one_or_none()
        return None if row is None else ProjectActorFacts(row.state, row.project_role)

    def owner_project_id(self, transaction: object, *, target: str,
                         resource_id: uuid.UUID) -> uuid.UUID | None:
        session = _session(transaction)
        if target == "MEMBER":
            statement = select(ProjectMemberRow.project_id).where(
                ProjectMemberRow.project_member_id == resource_id,
            )
        elif target == "DEPARTMENT":
            statement = select(DepartmentRow.project_id).where(
                DepartmentRow.department_id == resource_id,
            )
        else:
            raise ValueError("unsupported Project target")
        return session.execute(statement).scalar_one_or_none()
