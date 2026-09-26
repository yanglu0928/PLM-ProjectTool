"""Auth-owned identity projection combined with an explicit Project-owned reader."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.session_view import (
    AuthorizedProjectSummary, LoginSessionView,
)
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class AuthorizedProjectsPort(Protocol):
    def for_user(self, transaction: object, user_id: uuid.UUID) -> tuple[AuthorizedProjectSummary, ...]: ...


class SqlAlchemySessionView:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 projects: AuthorizedProjectsPort) -> None:
        if unit_of_work is None or projects is None:
            raise ValueError("identity and project projection dependencies are required")
        self._uow, self._projects = unit_of_work, projects

    def resolve(self, user_id: uuid.UUID) -> LoginSessionView:
        if type(user_id) is not uuid.UUID or user_id.int == 0:
            raise ValueError("valid user identity is required")
        with self._uow() as transaction:
            session = transaction.session  # type: ignore[attr-defined]
            if not isinstance(session, Session) or not session.in_transaction():
                raise RuntimeError("active identity transaction is required")
            row = session.execute(select(
                UserRow.user_id, UserRow.username_display, UserRow.deployment_role,
            ).where(UserRow.user_id == user_id, UserRow.state == "ENABLED")).one_or_none()
            if row is None:
                raise LookupError("current user is unavailable")
            projects = self._projects.for_user(transaction, user_id)
            if (type(projects) is not tuple
                    or any(type(item) is not AuthorizedProjectSummary for item in projects)):
                raise RuntimeError("invalid project authorization projection")
            return LoginSessionView(row.user_id, row.username_display, row.deployment_role, projects)
