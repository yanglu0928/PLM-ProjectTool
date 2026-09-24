"""Conditional Project writes using the caller's locked authorization transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.read_projects import ProjectView
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Project write transaction is required")
    return session


def _view(row: object) -> ProjectView:
    return ProjectView(row.project_id, row.project_code, row.name, row.state,
                       row.created_at, f'"v{row.lock_version}"')


class SqlAlchemyProjectWriteRepository:
    def patch_name(self, transaction: object, *, project_id: uuid.UUID,
                   expected_version: int, name: str) -> ProjectView | None:
        return self._change(transaction, project_id=project_id,
                            expected_version=expected_version, values={"name": name})

    def archive(self, transaction: object, *, project_id: uuid.UUID,
                expected_version: int) -> ProjectView | None:
        return self._change(transaction, project_id=project_id,
                            expected_version=expected_version, values={"state": "ARCHIVED"})

    @staticmethod
    def _change(transaction: object, *, project_id: uuid.UUID, expected_version: int,
                values: dict[str, str]) -> ProjectView | None:
        row = _session(transaction).execute(update(ProjectRow).where(
            ProjectRow.project_id == project_id,
            ProjectRow.state == "ACTIVE",
            ProjectRow.lock_version == expected_version,
        ).values(
            **values, lock_version=ProjectRow.lock_version + 1,
            updated_at=func.statement_timestamp(),
        ).returning(
            ProjectRow.project_id, ProjectRow.project_code, ProjectRow.name,
            ProjectRow.state, ProjectRow.created_at, ProjectRow.lock_version,
        )).one_or_none()
        return None if row is None else _view(row)
