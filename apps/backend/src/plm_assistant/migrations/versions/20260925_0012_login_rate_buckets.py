"""Short-lived login rate-limit windows.

Revision ID: 20260925_0012
Revises: 20260924_0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0012"
down_revision = "20260924_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_rate_buckets",
        sa.Column("bucket_key", sa.LargeBinary(length=32), primary_key=True),
        sa.Column("window_started_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.Column("last_attempt_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("octet_length(bucket_key) = 32", name="ck_auth_login_rate_buckets__key_size"),
        sa.CheckConstraint("attempt_count BETWEEN 1 AND 30", name="ck_auth_login_rate_buckets__count"),
        sa.CheckConstraint("last_attempt_at >= window_started_at", name="ck_auth_login_rate_buckets__time"),
        schema="plm",
    )
    op.create_index("ix_auth_login_rate_buckets__last_attempt", "auth_login_rate_buckets",
                    ["last_attempt_at"], schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("login rate bucket downgrade requires a live database")
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.auth_login_rate_buckets)")):
        raise RuntimeError("clear login rate buckets in a maintenance window before downgrade")
    op.drop_index("ix_auth_login_rate_buckets__last_attempt", table_name="auth_login_rate_buckets", schema="plm")
    op.drop_table("auth_login_rate_buckets", schema="plm")
