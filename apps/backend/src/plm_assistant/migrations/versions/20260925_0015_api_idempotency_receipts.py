"""Add cross-module persistent API replay receipts.

Revision ID: 20260925_0015
Revises: 20260925_0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0015"
down_revision = "20260925_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plt_idempotency_receipts",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("key_digest", sa.LargeBinary(), nullable=False),
        sa.Column("request_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("result_ref_type", sa.Text()),
        sa.Column("result_ref_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_status", sa.Integer()),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("actor_id", "project_id", "operation", "key_digest", name="uq_plt_idem_receipts__scope", postgresql_nulls_not_distinct=True),
        sa.CheckConstraint("operation ~ '^V[1-9][0-9]*_[A-Z][A-Z0-9_]{2,120}$' AND char_length(operation) <= 128", name="ck_plt_idem_receipts__operation"),
        sa.CheckConstraint("state IN ('PENDING', 'COMPLETED')", name="ck_plt_idem_receipts__state"),
        sa.CheckConstraint("octet_length(key_digest) = 32", name="ck_plt_idem_receipts__key_digest"),
        sa.CheckConstraint("octet_length(request_fingerprint) = 32", name="ck_plt_idem_receipts__fingerprint"),
        sa.CheckConstraint("(state = 'PENDING' AND result_ref_type IS NULL AND result_ref_id IS NULL AND result_status IS NULL AND completed_at IS NULL) OR (state = 'COMPLETED' AND result_ref_type ~ '^V[1-9][0-9]*_[A-Z][A-Z0-9_]{2,120}$' AND char_length(result_ref_type) <= 128 AND result_ref_id IS NOT NULL AND result_status BETWEEN 200 AND 299 AND completed_at IS NOT NULL)", name="ck_plt_idem_receipts__result"),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.reject_idempotency_receipt_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.state = 'COMPLETED' THEN
                RAISE EXCEPTION 'idempotency receipt is immutable';
            END IF;
            IF NEW.state <> 'COMPLETED'
               OR NEW.actor_id IS DISTINCT FROM OLD.actor_id
               OR NEW.project_id IS DISTINCT FROM OLD.project_id
               OR NEW.operation IS DISTINCT FROM OLD.operation
               OR NEW.key_digest IS DISTINCT FROM OLD.key_digest
               OR NEW.request_fingerprint IS DISTINCT FROM OLD.request_fingerprint
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'invalid idempotency receipt transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_plt_idem_receipts_immutable
        BEFORE UPDATE OR DELETE ON plm.plt_idempotency_receipts
        FOR EACH ROW EXECUTE FUNCTION plm.reject_idempotency_receipt_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for idempotency receipts")
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.plt_idempotency_receipts)")):
        raise RuntimeError("idempotency receipts exist; downgrade refused")
    op.execute("DROP TRIGGER trg_plt_idem_receipts_immutable ON plm.plt_idempotency_receipts")
    op.execute("DROP FUNCTION plm.reject_idempotency_receipt_mutation()")
    op.drop_table("plt_idempotency_receipts", schema="plm")
