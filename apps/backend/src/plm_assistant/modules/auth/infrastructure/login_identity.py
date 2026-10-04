"""Identity-only login lookup; the Session service rechecks the credential."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyLoginIdentity:
    def find_active(self, transaction: object, normalized_username: str) -> uuid.UUID | None:
        if type(normalized_username) is not str or not 1 <= len(normalized_username) <= 128:
            return None
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active login identity transaction is required")
        return session.execute(select(UserRow.user_id).where(
            UserRow.username_normalized == normalized_username,
            UserRow.state == "ENABLED",
            UserRow.credential_version > 0,
            UserRow.active_password_credential_id.is_not(None),
        )).scalar_one_or_none()
