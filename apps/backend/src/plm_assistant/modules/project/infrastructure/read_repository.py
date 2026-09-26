"""Project-owned fresh member-scope read queries."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.read_projects import ProjectView
from plm_assistant.modules.project.infrastructure.orm import (
    DepartmentRow, ProjectMemberRow, ProjectRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Project transaction is required")
    return session


def _view(row: object) -> ProjectView:
    return ProjectView(row.project_id, row.project_code, row.name,
                       row.state, row.created_at, f'"v{row.lock_version}"')


class SqlAlchemyProjectReadRepository:
    @staticmethod
    def _authorized(user_id: uuid.UUID):
        return select(
            ProjectRow.project_id, ProjectRow.project_code, ProjectRow.name,
            ProjectRow.state, ProjectRow.created_at, ProjectRow.lock_version,
        ).join(
            ProjectMemberRow, ProjectMemberRow.project_id == ProjectRow.project_id,
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
            ProjectRow.state.in_(("ACTIVE", "ARCHIVED")),
        )

    def list_authorized(self, transaction: object, user_id: uuid.UUID) -> tuple[ProjectView, ...]:
        rows = _session(transaction).execute(
            self._authorized(user_id).order_by(ProjectRow.project_id).limit(2),
        ).all()
        if len(rows) > 1:
            raise RuntimeError("ambiguous current Project membership")
        return tuple(_view(row) for row in rows)

    def get_authorized(self, transaction: object, user_id: uuid.UUID,
                       project_id: uuid.UUID) -> ProjectView | None:
        row = _session(transaction).execute(
            self._authorized(user_id).where(ProjectRow.project_id == project_id),
        ).one_or_none()
        return None if row is None else _view(row)
