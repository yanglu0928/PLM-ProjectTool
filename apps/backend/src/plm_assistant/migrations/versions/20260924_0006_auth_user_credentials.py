"""AUT-01 deployment User identity and immutable credential history."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0006"
down_revision = "20260924_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("username_display", sa.Text(), nullable=False),
        sa.Column("username_normalized", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'DISABLED'")),
        sa.Column("deployment_role", sa.Text(), nullable=False, server_default=sa.text("'NONE'")),
        sa.Column("credential_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("active_password_credential_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("retention_policy_id", postgresql.UUID(as_uuid=True)),
        sa.Column("retention_due_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("username_normalized", name="uq_auth_users__username_norm"),
        sa.CheckConstraint("char_length(username_display) BETWEEN 1 AND 255", name="ck_auth_users__username_display"),
        sa.CheckConstraint("char_length(username_normalized) BETWEEN 1 AND 128 AND username_normalized = btrim(username_normalized)", name="ck_auth_users__username_norm"),
        sa.CheckConstraint("state IN ('ENABLED', 'DISABLED')", name="ck_auth_users__state"),
        sa.CheckConstraint("deployment_role IN ('NONE', 'DEPLOYMENT_ADMIN')", name="ck_auth_users__deployment_role"),
        sa.CheckConstraint("(credential_version = 0 AND active_password_credential_id IS NULL AND state = 'DISABLED') OR (credential_version > 0 AND active_password_credential_id IS NOT NULL)", name="ck_auth_users__credential_shape"),
        sa.CheckConstraint("lock_version >= 0", name="ck_auth_users__lock_version"),
        schema="plm",
    )
    op.create_table(
        "auth_password_credentials",
        sa.Column("password_credential_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_version", sa.BigInteger(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("algorithm_id", sa.Text(), nullable=False),
        sa.Column("parameter_set", postgresql.JSONB(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("changed_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(["user_id"], ["plm.auth_users.user_id"], name="fk_auth_pwd__user", ondelete="NO ACTION"),
        sa.UniqueConstraint("user_id", "credential_version"),
        sa.UniqueConstraint("password_credential_id", "user_id", "credential_version"),
        sa.CheckConstraint("credential_version > 0", name="ck_auth_pwd__credential_version"),
        sa.CheckConstraint("char_length(password_hash) BETWEEN 1 AND 1024", name="ck_auth_pwd__password_hash"),
        sa.CheckConstraint("algorithm_id ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_auth_pwd__algorithm_id"),
        sa.CheckConstraint("jsonb_typeof(parameter_set) = 'object'", name="ck_auth_pwd__parameter_set"),
        schema="plm",
    )
    op.create_foreign_key(
        "fk_auth_users__active_credential", "auth_users", "auth_password_credentials",
        ["active_password_credential_id", "user_id", "credential_version"],
        ["password_credential_id", "user_id", "credential_version"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
    )
    op.execute("""
        CREATE FUNCTION plm.reject_password_credential_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'password credential history is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_auth_pwd_no_update_delete
        BEFORE UPDATE OR DELETE ON plm.auth_password_credentials
        FOR EACH ROW EXECUTE FUNCTION plm.reject_password_credential_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_auth_pwd_no_truncate
        BEFORE TRUNCATE ON plm.auth_password_credentials
        FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_password_credential_mutation()
    """)
    op.execute("""
        CREATE FUNCTION plm.reject_auth_credential_version_regression()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.credential_version < OLD.credential_version THEN
                RAISE EXCEPTION 'credential version cannot regress';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_auth_users_credential_version_monotonic
        BEFORE UPDATE ON plm.auth_users
        FOR EACH ROW EXECUTE FUNCTION plm.reject_auth_credential_version_regression()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: identity history must be checked")
    bind = op.get_bind()
    for table in ("auth_password_credentials", "auth_users"):
        if bind.scalar(sa.text(f"SELECT count(*) FROM plm.{table}")):
            raise RuntimeError("auth identity data exists; downgrade refused")
    op.execute("DROP TRIGGER trg_auth_users_credential_version_monotonic ON plm.auth_users")
    op.execute("DROP FUNCTION plm.reject_auth_credential_version_regression()")
    op.execute("DROP TRIGGER trg_auth_pwd_no_truncate ON plm.auth_password_credentials")
    op.execute("DROP TRIGGER trg_auth_pwd_no_update_delete ON plm.auth_password_credentials")
    op.execute("DROP FUNCTION plm.reject_password_credential_mutation()")
    op.drop_constraint("fk_auth_users__active_credential", "auth_users", schema="plm", type_="foreignkey")
    op.drop_table("auth_password_credentials", schema="plm")
    op.drop_table("auth_users", schema="plm")
