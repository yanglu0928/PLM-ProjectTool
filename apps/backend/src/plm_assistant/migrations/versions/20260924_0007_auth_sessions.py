"""AUT-02 server-side Session metadata with digest-only security materials."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0007"
down_revision = "20260924_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("session_token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_digest", sa.LargeBinary(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("absolute_expires_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.Column("idle_expires_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("revoke_reason", sa.Text()),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("retention_due_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("session_token_digest", name="uq_auth_sessions__token_digest"),
        sa.ForeignKeyConstraint(
            ["user_id", "credential_version"],
            ["plm.auth_password_credentials.user_id", "plm.auth_password_credentials.credential_version"],
            name="fk_auth_sessions__credential", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("octet_length(session_token_digest) = 32", name="ck_auth_sessions__token_digest"),
        sa.CheckConstraint("octet_length(csrf_digest) = 32", name="ck_auth_sessions__csrf_digest"),
        sa.CheckConstraint("credential_version > 0", name="ck_auth_sessions__credential_version"),
        sa.CheckConstraint("created_at <= last_seen_at AND last_seen_at < idle_expires_at AND idle_expires_at <= absolute_expires_at", name="ck_auth_sessions__time_order"),
        sa.CheckConstraint("(revoked_at IS NULL AND revoke_reason IS NULL) OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL AND revoked_at >= created_at AND revoke_reason ~ '^[A-Z][A-Z0-9_]{0,63}$')", name="ck_auth_sessions__revoke_shape"),
        sa.CheckConstraint("lock_version >= 0", name="ck_auth_sessions__lock_version"),
        schema="plm",
    )
    op.create_index("ix_auth_sessions__user_revoked", "auth_sessions", ["user_id", "revoked_at"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_auth_session_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.session_token_digest IS DISTINCT FROM OLD.session_token_digest
               OR NEW.csrf_digest IS DISTINCT FROM OLD.csrf_digest
               OR NEW.user_id IS DISTINCT FROM OLD.user_id
               OR NEW.credential_version IS DISTINCT FROM OLD.credential_version
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.absolute_expires_at IS DISTINCT FROM OLD.absolute_expires_at
               OR NEW.last_seen_at < OLD.last_seen_at
               OR NEW.idle_expires_at < OLD.idle_expires_at
               OR NEW.lock_version <= OLD.lock_version
               OR (OLD.revoked_at IS NOT NULL AND (
                   NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                   OR NEW.revoke_reason IS DISTINCT FROM OLD.revoke_reason
                   OR NEW.last_seen_at IS DISTINCT FROM OLD.last_seen_at
                   OR NEW.idle_expires_at IS DISTINCT FROM OLD.idle_expires_at
               )) THEN
                RAISE EXCEPTION 'invalid session transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_auth_sessions_guard_update
        BEFORE UPDATE ON plm.auth_sessions
        FOR EACH ROW EXECUTE FUNCTION plm.guard_auth_session_update()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: session data must be checked")
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM plm.auth_sessions")):
        raise RuntimeError("session data exists; downgrade refused")
    op.execute("DROP TRIGGER trg_auth_sessions_guard_update ON plm.auth_sessions")
    op.execute("DROP FUNCTION plm.guard_auth_session_update()")
    op.drop_index("ix_auth_sessions__user_revoked", table_name="auth_sessions", schema="plm")
    op.drop_table("auth_sessions", schema="plm")
