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


class UserCreateResultRow(Base):
    """Private source coordinates and safe first response, never credential hashes."""
    __tablename__ = 'auth_user_create_results'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['plm.auth_users.user_id'], name='fk_auth_create__user'),
        ForeignKeyConstraint(['actor_id'], ['plm.auth_users.user_id'], name='fk_auth_create__actor'),
        ForeignKeyConstraint(['credential_id', 'user_id', 'credential_version'],
            ['plm.auth_password_credentials.password_credential_id', 'plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'], name='fk_auth_create__credential'),
        ForeignKeyConstraint(['audit_event_id'], ['plm.aud_events.audit_event_id'], name='fk_auth_create__audit'),
        UniqueConstraint('credential_id', name='uq_auth_create__credential'),
        UniqueConstraint('audit_event_id', name='uq_auth_create__audit'),
        CheckConstraint(" AND ".join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid"
            for c in ('user_id','credential_id','actor_id','audit_event_id','trace_id'))
            + " AND user_id<>actor_id AND char_length(username_display) BETWEEN 1 AND 255"
            + " AND account_state='ENABLED' AND deployment_role='NONE' AND credential_version=1 AND lock_version=1"
            + " AND isfinite(created_at) AND isfinite(updated_at) AND isfinite(accepted_at)"
            + " AND created_at<=updated_at AND updated_at<=accepted_at", name='ck_auth_create__shape'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    username_display: Mapped[str] = mapped_column(Text, nullable=False)
    account_state: Mapped[str] = mapped_column(Text, nullable=False)
    deployment_role: Mapped[str] = mapped_column(Text, nullable=False)
    credential_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text('statement_timestamp()'))


class UserStateResultRow(Base):
    """Auth-owned first state response and private audit/source coordinates."""
    __tablename__='auth_user_state_results'
    __table_args__=(
        ForeignKeyConstraint(['user_id'],['plm.auth_users.user_id'],name='fk_auth_state__user'),
        ForeignKeyConstraint(['actor_id'],['plm.auth_users.user_id'],name='fk_auth_state__actor'),
        ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_auth_state__audit'),
        UniqueConstraint('user_id','lock_version',name='uq_auth_state__user_version'),
        UniqueConstraint('audit_event_id',name='uq_auth_state__audit'),
        CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in
            ('result_id','user_id','actor_id','audit_event_id','trace_id'))
            + " AND char_length(username_display) BETWEEN 1 AND 255"
            + " AND deployment_role IN ('NONE','DEPLOYMENT_ADMIN') AND credential_version>0"
            + " AND expected_version BETWEEN 0 AND 9223372036854775806 AND lock_version>0"
            + " AND lock_version-1=expected_version AND revoked_session_count>=0"
            + " AND ((operation='ENABLE' AND account_state='ENABLED' AND revoked_session_count=0)"
            + " OR (operation='DISABLE' AND account_state='DISABLED'))"
            + " AND isfinite(created_at) AND isfinite(updated_at) AND isfinite(accepted_at)"
            + " AND created_at<=updated_at AND updated_at<=accepted_at",name='ck_auth_state__shape'),
    )
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    operation: Mapped[str] = mapped_column(Text,nullable=False)
    username_display: Mapped[str] = mapped_column(Text,nullable=False)
    account_state: Mapped[str] = mapped_column(Text,nullable=False)
    deployment_role: Mapped[str] = mapped_column(Text,nullable=False)
    expected_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    credential_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    revoked_session_count: Mapped[int] = mapped_column(BigInteger,nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False,
        server_default=text('statement_timestamp()'))


class PasswordChangeResultRow(Base):
    """Immutable first password-change response and private credential source."""
    __tablename__='auth_password_change_results'
    __table_args__=(
        ForeignKeyConstraint(['user_id'],['plm.auth_users.user_id'],name='fk_auth_change__user'),
        ForeignKeyConstraint(['before_credential_id','user_id','before_credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_change__before'),
        ForeignKeyConstraint(['credential_id','user_id','credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_change__after'),
        ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_auth_change__audit'),
        UniqueConstraint('user_id','credential_version',name='uq_auth_change__credential'),
        UniqueConstraint('user_id','user_version',name='uq_auth_change__user_version'),
        UniqueConstraint('audit_event_id',name='uq_auth_change__audit'),
        CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in
            ('result_id','user_id','before_credential_id','credential_id','audit_event_id','trace_id'))
            + ' AND before_credential_id<>credential_id'
            + ' AND before_credential_version BETWEEN 1 AND 9223372036854775806'
            + ' AND credential_version>1 AND credential_version-1=before_credential_version'
            + ' AND before_user_version BETWEEN 0 AND 9223372036854775806'
            + ' AND user_version>0 AND user_version-1=before_user_version AND revoked_session_count>0'
            + ' AND isfinite(changed_at) AND isfinite(accepted_at) AND changed_at<=accepted_at',name='ck_auth_change__shape'),
    )
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    before_credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    before_credential_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    credential_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    before_user_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    user_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    revoked_session_count: Mapped[int] = mapped_column(BigInteger,nullable=False)
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False,
        server_default=text('statement_timestamp()'))


class PasswordResetResultRow(Base):
    """Immutable administrator reset first, not current authorization."""
    __tablename__='auth_password_reset_results'
    __table_args__=(
        ForeignKeyConstraint(['user_id'],['plm.auth_users.user_id'],name='fk_auth_reset__user'),
        ForeignKeyConstraint(['actor_id'],['plm.auth_users.user_id'],name='fk_auth_reset__actor'),
        ForeignKeyConstraint(['before_credential_id','user_id','before_credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_reset__before'),
        ForeignKeyConstraint(['credential_id','user_id','credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_reset__after'),
        ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_auth_reset__audit'),
        UniqueConstraint('user_id','credential_version',name='uq_auth_reset__credential'),
        UniqueConstraint('user_id','user_version',name='uq_auth_reset__user_version'),
        UniqueConstraint('audit_event_id',name='uq_auth_reset__audit'),
        CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in
            ('result_id','user_id','actor_id','before_credential_id','credential_id','audit_event_id','trace_id'))
            + ' AND before_credential_id<>credential_id'
            + ' AND before_credential_version BETWEEN 1 AND 9223372036854775806'
            + ' AND credential_version>1 AND credential_version-1=before_credential_version'
            + ' AND before_user_version BETWEEN 0 AND 9223372036854775806'
            + ' AND user_version>0 AND user_version-1=before_user_version AND revoked_session_count>=0'
            + " AND target_state IN ('ENABLED','DISABLED')"
            + ' AND isfinite(changed_at) AND isfinite(accepted_at) AND changed_at<=accepted_at',name='ck_auth_reset__shape'),
    )
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    before_credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    before_credential_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    credential_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    before_user_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    user_version: Mapped[int] = mapped_column(BigInteger,nullable=False)
    target_state: Mapped[str] = mapped_column(Text,nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    revoked_session_count: Mapped[int] = mapped_column(BigInteger,nullable=False)
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True,precision=6),nullable=False,
        server_default=text('statement_timestamp()'))
