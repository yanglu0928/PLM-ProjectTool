"""Serialize first-user creation and persist the administrator atomically."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult
from plm_assistant.modules.auth.infrastructure.user_orm import PasswordCredentialRow, UserRow


_BOOTSTRAP_LOCK = 0x504C4D494E495441  # Dedicated transaction advisory lock key.


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active bootstrap transaction is required")
    return session


class SqlAlchemyInitialAdminRepository:
    def claim_empty(self, transaction: object) -> bool:
        session = _session(transaction)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK})
        return session.scalar(select(func.count()).select_from(UserRow)) == 0

    def create(self, transaction: object, *, username_display: str,
               username_normalized: str, hashed: PasswordHashResult) -> uuid.UUID:
        session = _session(transaction)
        user_id = session.execute(insert(UserRow).values(
            username_display=username_display, username_normalized=username_normalized,
            state="DISABLED", deployment_role="NONE",
        ).returning(UserRow.user_id)).scalar_one()
        credential_id = session.execute(insert(PasswordCredentialRow).values(
            user_id=user_id, credential_version=1, password_hash=hashed.password_hash,
            algorithm_id=hashed.algorithm_id, parameter_set=dict(hashed.parameter_set),
            must_change_password=False,
        ).returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        count = session.execute(update(UserRow).where(
            UserRow.user_id == user_id, UserRow.state == "DISABLED",
            UserRow.credential_version == 0,
        ).values(
            state="ENABLED", deployment_role="DEPLOYMENT_ADMIN",
            credential_version=1, active_password_credential_id=credential_id,
            lock_version=1,
        )).rowcount
        if count != 1:
            raise RuntimeError("initial admin activation failed")
        return user_id
