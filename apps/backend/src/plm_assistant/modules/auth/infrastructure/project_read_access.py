"""Auth-owned current Session/User proof for Project GET operations."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyProjectReadAccess:
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None:
        if (type(session_token) is not bytes or len(session_token) != 32
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            return None
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Auth transaction is required")
        return session.execute(select(SessionRow.user_id).join(
            UserRow, SessionRow.user_id == UserRow.user_id,
        ).where(
            SessionRow.session_token_digest == hashlib.sha256(session_token).digest(),
            SessionRow.revoked_at.is_(None),
            SessionRow.created_at <= now,
            SessionRow.idle_expires_at > now,
            SessionRow.absolute_expires_at > now,
            UserRow.state == "ENABLED",
            UserRow.credential_version == SessionRow.credential_version,
        ).with_for_update(read=True, of=(SessionRow, UserRow))).scalar_one_or_none()
