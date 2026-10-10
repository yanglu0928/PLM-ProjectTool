"""PostgreSQL adapter for AUT-02 session lifecycle."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.application.session_service import SessionRecord
from plm_assistant.modules.auth.infrastructure.session_orm import SessionRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("active auth transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active auth transaction is required")
    return session


class SqlAlchemySessionRepository:
    def lock_user(self, transaction: object, user_id: uuid.UUID) -> bool:
        return _session(transaction).execute(
            select(UserRow.user_id).where(UserRow.user_id == user_id).with_for_update()
        ).scalar_one_or_none() is not None

    def current_credential_version(self, transaction: object, user_id: uuid.UUID) -> int | None:
        return _session(transaction).execute(
            select(UserRow.credential_version).where(
                UserRow.user_id == user_id, UserRow.state == "ENABLED",
                UserRow.credential_version > 0,
            ).with_for_update()
        ).scalar_one_or_none()

    def create(self, transaction: object, *, user_id: uuid.UUID, credential_version: int,
               token_digest: bytes, csrf_digest: bytes, now: datetime,
               absolute_expires_at: datetime, idle_expires_at: datetime) -> uuid.UUID:
        return _session(transaction).execute(
            insert(SessionRow).values(
                user_id=user_id, credential_version=credential_version,
                session_token_digest=token_digest, csrf_digest=csrf_digest,
                created_at=now, last_seen_at=now,
                absolute_expires_at=absolute_expires_at, idle_expires_at=idle_expires_at,
                lock_version=0,
            ).returning(SessionRow.session_id)
        ).scalar_one()

    def find_by_token_digest(self, transaction: object, digest: bytes) -> SessionRecord | None:
        row = _session(transaction).execute(
            select(
                SessionRow.session_id, SessionRow.user_id, SessionRow.credential_version,
                SessionRow.csrf_digest, SessionRow.absolute_expires_at,
                SessionRow.idle_expires_at, SessionRow.revoked_at,
                UserRow.state, UserRow.credential_version, SessionRow.revoke_reason,
            ).join(UserRow, SessionRow.user_id == UserRow.user_id)
            .where(SessionRow.session_token_digest == digest)
        ).one_or_none()
        return SessionRecord(*row) if row is not None else None

    def revoke(self, transaction: object, session_id: uuid.UUID, now: datetime, reason: str) -> bool:
        result = _session(transaction).execute(
            update(SessionRow).where(
                SessionRow.session_id == session_id,
                SessionRow.revoked_at.is_(None),
                SessionRow.absolute_expires_at > now,
                SessionRow.idle_expires_at > now,
                and_(
                    UserRow.user_id == SessionRow.user_id,
                    UserRow.state == "ENABLED",
                    UserRow.credential_version == SessionRow.credential_version,
                ),
            ).values(revoked_at=now, revoke_reason=reason,
                     lock_version=SessionRow.lock_version + 1)
        )
        return result.rowcount == 1

    def revoke_user_sessions(self, transaction: object, user_id: uuid.UUID, now: datetime, reason: str) -> int:
        result = _session(transaction).execute(
            update(SessionRow).where(
                SessionRow.user_id == user_id,
                SessionRow.revoked_at.is_(None),
                SessionRow.created_at <= now,
            ).values(revoked_at=now, revoke_reason=reason,
                     lock_version=SessionRow.lock_version + 1)
        )
        return result.rowcount
