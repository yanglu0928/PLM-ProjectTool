"""Auth-owned identity projection combined with an explicit Project-owned reader."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.session_view import (
    AuthorizedProjectSummary, LoginSessionView,
)
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow, PasswordCredentialRow
from .session_credential import SqlAlchemySessionCredentialFacts


class AuthorizedProjectsPort(Protocol):
    def for_user(self, transaction: object, user_id: uuid.UUID) -> tuple[AuthorizedProjectSummary, ...]: ...


class SqlAlchemySessionView:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 projects: AuthorizedProjectsPort) -> None:
        if unit_of_work is None or projects is None:
            raise ValueError("identity and project projection dependencies are required")
        self._uow, self._projects = unit_of_work, projects

    def resolve_for_session(self, *, user_id, session_token):
        with self._uow() as transaction:
            fact = SqlAlchemySessionCredentialFacts().get(transaction, session_token=session_token,
                now=datetime.now(timezone.utc))
            if fact is None or fact.user_id != user_id:
                raise LookupError('Current Session unavailable')
            return self._resolve(transaction, user_id, fact)

    def resolve(self, user_id: uuid.UUID) -> LoginSessionView:
        if type(user_id) is not uuid.UUID or user_id.int == 0:
            raise ValueError("valid user identity is required")
        with self._uow() as transaction:
            return self._resolve(transaction, user_id)

    def _resolve(self, transaction, user_id, fact=None):
        session = transaction.session
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError('Active identity transaction required')
        row = session.execute(select(UserRow.user_id, UserRow.username_display, UserRow.deployment_role,
            PasswordCredentialRow.must_change_password, UserRow.credential_version,
            UserRow.active_password_credential_id).join(PasswordCredentialRow,
                UserRow.active_password_credential_id == PasswordCredentialRow.password_credential_id)
            .where(UserRow.user_id == user_id, UserRow.state == 'ENABLED',
                PasswordCredentialRow.user_id == UserRow.user_id,
                PasswordCredentialRow.credential_version == UserRow.credential_version)
            .with_for_update(read=True, of=UserRow)).one_or_none()
        if row is None or type(row.must_change_password) is not bool:
            raise LookupError('Current credential unavailable')
        if fact is not None and (fact.credential_version != row.credential_version
            or fact.credential_id != row.active_password_credential_id
            or fact.password_change_required != row.must_change_password):
            raise LookupError('Current credential binding unavailable')
        if row.must_change_password:
            return LoginSessionView(row.user_id, row.username_display, 'NONE', (), True)
        projects = self._projects.for_user(transaction, user_id)
        if type(projects) is not tuple or any(type(item) is not AuthorizedProjectSummary for item in projects):
            raise RuntimeError('Invalid project authorization projection')
        return LoginSessionView(row.user_id, row.username_display, row.deployment_role, projects, False)
