"""Persist PLT-01 command replay receipts without storing raw request keys."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0004"
down_revision = "20260924_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plt_configuration_command_receipts",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("key_digest", sa.LargeBinary(), nullable=False),
        sa.Column("request_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("result_configuration_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_version_no", sa.Integer()),
        sa.Column("result_lock_version", sa.BigInteger()),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("actor_id", "operation", "key_digest"),
        sa.ForeignKeyConstraint(["result_configuration_id"], ["plm.plt_system_configurations.system_configuration_id"], name="fk_plt_cfg_receipt__config", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["result_version_id", "result_configuration_id"], ["plm.plt_configuration_versions.configuration_version_id", "plm.plt_configuration_versions.system_configuration_id"], name="fk_plt_cfg_receipt__version", ondelete="NO ACTION"),
        sa.CheckConstraint("operation IN ('CREATE', 'CREATE_VERSION', 'ACTIVATE')", name="ck_plt_cfg_receipt__operation"),
        sa.CheckConstraint("state IN ('PENDING', 'COMPLETED')", name="ck_plt_cfg_receipt__state"),
        sa.CheckConstraint("octet_length(key_digest) = 32", name="ck_plt_cfg_receipt__key_digest"),
        sa.CheckConstraint("octet_length(request_fingerprint) = 32", name="ck_plt_cfg_receipt__request_fingerprint"),
        sa.CheckConstraint("(state = 'PENDING' AND result_configuration_id IS NULL AND result_version_id IS NULL AND result_version_no IS NULL AND result_lock_version IS NULL AND completed_at IS NULL) OR (state = 'COMPLETED' AND result_configuration_id IS NOT NULL AND result_lock_version >= 0 AND completed_at IS NOT NULL AND ((result_version_id IS NULL AND result_version_no IS NULL) OR (result_version_id IS NOT NULL AND result_version_no > 0)))", name="ck_plt_cfg_receipt__result_shape"),
        schema="plm",
    )
    op.create_index(
        "ix_plt_cfg_receipt__result_config",
        "plt_configuration_command_receipts",
        ["result_configuration_id"], schema="plm",
    )
    op.create_index(
        "ix_plt_cfg_receipt__result_version",
        "plt_configuration_command_receipts",
        ["result_version_id", "result_configuration_id"], schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.reject_configuration_receipt_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.state = 'COMPLETED' THEN
                RAISE EXCEPTION 'completed configuration receipts are immutable';
            END IF;
            IF NEW.state <> 'COMPLETED'
               OR NEW.actor_id IS DISTINCT FROM OLD.actor_id
               OR NEW.operation IS DISTINCT FROM OLD.operation
               OR NEW.key_digest IS DISTINCT FROM OLD.key_digest
               OR NEW.request_fingerprint IS DISTINCT FROM OLD.request_fingerprint
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'invalid configuration receipt transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_plt_cfg_receipts_immutable
        BEFORE UPDATE OR DELETE ON plm.plt_configuration_command_receipts
        FOR EACH ROW EXECUTE FUNCTION plm.reject_configuration_receipt_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: replay receipts must be checked")
    count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM plm.plt_configuration_command_receipts")
    )
    if count:
        raise RuntimeError("configuration replay receipts exist; downgrade refused")
    op.execute("DROP TRIGGER trg_plt_cfg_receipts_immutable ON plm.plt_configuration_command_receipts")
    op.execute("DROP FUNCTION plm.reject_configuration_receipt_mutation()")
    op.drop_table("plt_configuration_command_receipts", schema="plm")
