"""AUT-01 PostgreSQL identity creation; all writes use caller-owned transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.user_commands import PasswordHashResult
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordCredentialRow, UserRow


class AuthTransactionError(RuntimeError):
    """No active SQLAlchemy transaction was provided."""


def _session(transaction: object):
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise AuthTransactionError("active auth transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise AuthTransactionError("active auth transaction is required")
    return session


class SqlAlchemyUserRepository:
    def add_user(self, transaction: object, *, username_display: str, username_normalized: str, actor_id: uuid.UUID) -> uuid.UUID | None:
        return _session(transaction).execute(
            pg_insert(UserRow).values(
                username_display=username_display, username_normalized=username_normalized,
                state="DISABLED", deployment_role="NONE", created_by=actor_id, updated_by=actor_id,
            ).on_conflict_do_nothing(index_elements=["username_normalized"])
            .returning(UserRow.user_id)
        ).scalar_one_or_none()

    def add_credential(self, transaction: object, *, user_id: uuid.UUID, password_hash: PasswordHashResult, actor_id: uuid.UUID) -> uuid.UUID:
        return _session(transaction).execute(
            pg_insert(PasswordCredentialRow).values(
                user_id=user_id, credential_version=1,
                password_hash=password_hash.password_hash,
                algorithm_id=password_hash.algorithm_id,
                parameter_set=dict(password_hash.parameter_set),
                must_change_password=False, changed_by=actor_id,
            ).returning(PasswordCredentialRow.password_credential_id)
        ).scalar_one()

    def activate_initial_credential(self, transaction: object, *, user_id: uuid.UUID, credential_id: uuid.UUID, actor_id: uuid.UUID) -> bool:
        result = _session(transaction).execute(
            update(UserRow).where(
                UserRow.user_id == user_id,
                UserRow.credential_version == 0,
                UserRow.active_password_credential_id.is_(None),
                UserRow.state == "DISABLED",
            ).values(
                active_password_credential_id=credential_id,
                credential_version=1, state="ENABLED", lock_version=1,
                updated_at=func.statement_timestamp(), updated_by=actor_id,
            )
        )
        return result.rowcount == 1
