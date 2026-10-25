"""Outbox delivery owner, expiry, fencing and bounded retry.

Revision ID: 20260926_0026
Revises: 20260926_0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260926_0026"
down_revision = "20260926_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.job_outbox_events WHERE delivery_state='DELIVERING')")):
            raise RuntimeError("legacy DELIVERING events need controlled recovery before upgrade")
    op.add_column("job_outbox_events", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("5")), schema="plm")
    op.add_column("job_outbox_events", sa.Column("delivery_token", sa.BigInteger(), nullable=False, server_default=sa.text("0")), schema="plm")
    op.add_column("job_outbox_events", sa.Column("delivery_owner", sa.Text()), schema="plm")
    op.add_column("job_outbox_events", sa.Column("delivery_expires_at", postgresql.TIMESTAMP(timezone=True, precision=6)), schema="plm")
    op.add_column("job_outbox_events", sa.Column("delivered_at", postgresql.TIMESTAMP(timezone=True, precision=6)), schema="plm")
    op.add_column("job_outbox_events", sa.Column("last_error_code", sa.Text()), schema="plm")
    op.create_check_constraint("ck_job_outbox_events__delivery_counters", "job_outbox_events", "max_attempts > 0 AND delivery_token >= 0", schema="plm")
    op.create_check_constraint("ck_job_outbox_events__lease_shape", "job_outbox_events", "(delivery_state='DELIVERING' AND delivery_owner IS NOT NULL AND delivery_expires_at IS NOT NULL) OR (delivery_state<>'DELIVERING' AND delivery_owner IS NULL AND delivery_expires_at IS NULL)", schema="plm")
    op.create_check_constraint("ck_job_outbox_events__delivery_owner", "job_outbox_events", "delivery_owner IS NULL OR (char_length(delivery_owner) BETWEEN 1 AND 128 AND delivery_owner=btrim(delivery_owner))", schema="plm")
    op.create_check_constraint("ck_job_outbox_events__error", "job_outbox_events", "last_error_code IS NULL OR char_length(last_error_code) BETWEEN 1 AND 64", schema="plm")
    op.create_index("ix_job_outbox__lease_expiry", "job_outbox_events", ["delivery_expires_at", "event_id"], schema="plm", postgresql_where=sa.text("delivery_state='DELIVERING'"))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for Outbox delivery lease")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.job_outbox_events WHERE delivery_token<>0 OR delivery_owner IS NOT NULL OR delivery_expires_at IS NOT NULL OR delivered_at IS NOT NULL OR last_error_code IS NOT NULL)")):
        raise RuntimeError("Outbox delivery history exists; downgrade refused")
    op.drop_index("ix_job_outbox__lease_expiry", table_name="job_outbox_events", schema="plm")
    for constraint in ("ck_job_outbox_events__error", "ck_job_outbox_events__delivery_owner", "ck_job_outbox_events__lease_shape", "ck_job_outbox_events__delivery_counters"):
        op.drop_constraint(constraint, "job_outbox_events", schema="plm", type_="check")
    for column in ("last_error_code", "delivered_at", "delivery_expires_at", "delivery_owner", "delivery_token", "max_attempts"):
        op.drop_column("job_outbox_events", column, schema="plm")
