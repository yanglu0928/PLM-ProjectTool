"""AUT-01 User identity and immutable password-credential metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class UserRow(Base):
    __tablename__ = "auth_users"
    __table_args__ = (
        UniqueConstraint("username_normalized", name="uq_auth_users__username_norm"),
        ForeignKeyConstraint(
            ["active_password_credential_id", "user_id", "credential_version"],
            ["plm.auth_password_credentials.password_credential_id", "plm.auth_password_credentials.user_id", "plm.auth_password_credentials.credential_version"],
            name="fk_auth_users__active_credential", ondelete="NO ACTION", use_alter=True,
        ),
        CheckConstraint("char_length(username_display) BETWEEN 1 AND 255", name="ck_auth_users__username_display"),
        CheckConstraint("char_length(username_normalized) BETWEEN 1 AND 128 AND username_normalized = btrim(username_normalized)", name="ck_auth_users__username_norm"),
        CheckConstraint("state IN ('ENABLED', 'DISABLED')", name="ck_auth_users__state"),
        CheckConstraint("deployment_role IN ('NONE', 'DEPLOYMENT_ADMIN')", name="ck_auth_users__deployment_role"),
        CheckConstraint("(credential_version = 0 AND active_password_credential_id IS NULL AND state = 'DISABLED') OR (credential_version > 0 AND active_password_credential_id IS NOT NULL)", name="ck_auth_users__credential_shape"),
        CheckConstraint("lock_version >= 0", name="ck_auth_users__lock_version"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    username_display: Mapped[str] = mapped_column(Text, nullable=False)
    username_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DISABLED'"))
    deployment_role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'NONE'"))
    credential_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    active_password_credential_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retention_due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class PasswordCredentialRow(Base):
    __tablename__ = "auth_password_credentials"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["plm.auth_users.user_id"], name="fk_auth_pwd__user", ondelete="NO ACTION"),
        UniqueConstraint("user_id", "credential_version"),
        UniqueConstraint("password_credential_id", "user_id", "credential_version"),
        CheckConstraint("credential_version > 0", name="ck_auth_pwd__credential_version"),
        CheckConstraint("char_length(password_hash) BETWEEN 1 AND 1024", name="ck_auth_pwd__password_hash"),
        CheckConstraint("algorithm_id ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_auth_pwd__algorithm_id"),
        CheckConstraint("jsonb_typeof(parameter_set) = 'object'", name="ck_auth_pwd__parameter_set"),
    )

    password_credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    credential_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_id: Mapped[str] = mapped_column(Text, nullable=False)
    parameter_set: Mapped[Any] = mapped_column(JSONB, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
