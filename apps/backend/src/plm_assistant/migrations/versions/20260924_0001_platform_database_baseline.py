"""Establish the PostgreSQL 18 and pgvector platform baseline."""

from __future__ import annotations

from alembic import context, op
from sqlalchemy import text


revision = "20260924_0001"
down_revision = None
branch_labels = None
depends_on = None

PGVECTOR_VERSION = "0.8.6"


def upgrade() -> None:
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector "
        f"WITH SCHEMA public VERSION '{PGVECTOR_VERSION}'"
    )
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    installed_version = bind.scalar(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    )
    if installed_version != PGVECTOR_VERSION:
        raise RuntimeError(
            "pgvector version mismatch: "
            f"expected {PGVECTOR_VERSION}, received {installed_version}"
        )


def downgrade() -> None:
    # The empty plm schema/version table and pgvector extension are deployment
    # prerequisites shared by all later revisions. They intentionally remain at
    # Alembic base, matching the frozen DB Schema V1 recovery boundary.
    pass
