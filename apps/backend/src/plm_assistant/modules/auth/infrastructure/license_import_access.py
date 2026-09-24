"""Auth-owned Session/CSRF/DeploymentAdmin proof for License recovery import."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyLicenseImportAccess:
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(csrf_token) is not bytes or len(csrf_token) != 32
                or not isinstance(now, datetime) or now.tzinfo is None):
            return None
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as exc:
            raise RuntimeError("active auth transaction is required") from exc
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active auth transaction is required")
        row = session.execute(select(SessionRow.user_id, SessionRow.csrf_digest).join(
            UserRow, SessionRow.user_id == UserRow.user_id,
        ).where(
            SessionRow.session_token_digest == hashlib.sha256(session_token).digest(),
            SessionRow.revoked_at.is_(None),
            SessionRow.created_at <= now,
            SessionRow.idle_expires_at > now,
            SessionRow.absolute_expires_at > now,
            UserRow.state == "ENABLED",
            UserRow.deployment_role == "DEPLOYMENT_ADMIN",
            UserRow.credential_version == SessionRow.credential_version,
        ).with_for_update(of=(SessionRow, UserRow))).one_or_none()
        if row is None:
            return None
        if not hmac.compare_digest(row.csrf_digest, hashlib.sha256(csrf_token).digest()):
            return None
        return row.user_id
