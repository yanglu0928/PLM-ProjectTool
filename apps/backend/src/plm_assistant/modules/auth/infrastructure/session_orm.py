"""AUT-02 server-side Session facts; only token/CSRF digests persist."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class SessionRow(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("session_token_digest", name="uq_auth_sessions__token_digest"),
        ForeignKeyConstraint(
            ["user_id", "credential_version"],
            ["plm.auth_password_credentials.user_id", "plm.auth_password_credentials.credential_version"],
            name="fk_auth_sessions__credential", ondelete="NO ACTION",
        ),
        CheckConstraint("octet_length(session_token_digest) = 32", name="ck_auth_sessions__token_digest"),
        CheckConstraint("octet_length(csrf_digest) = 32", name="ck_auth_sessions__csrf_digest"),
        CheckConstraint("credential_version > 0", name="ck_auth_sessions__credential_version"),
        CheckConstraint("created_at <= last_seen_at AND last_seen_at < idle_expires_at AND idle_expires_at <= absolute_expires_at", name="ck_auth_sessions__time_order"),
        CheckConstraint("(revoked_at IS NULL AND revoke_reason IS NULL) OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL AND revoked_at >= created_at AND revoke_reason ~ '^[A-Z][A-Z0-9_]{0,63}$')", name="ck_auth_sessions__revoke_shape"),
        CheckConstraint("lock_version >= 0", name="ck_auth_sessions__lock_version"),
        Index("ix_auth_sessions__user_revoked", "user_id", "revoked_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    session_token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    csrf_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    credential_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    absolute_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retention_due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
