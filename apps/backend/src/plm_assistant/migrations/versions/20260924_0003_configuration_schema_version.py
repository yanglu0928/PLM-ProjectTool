"""Carry the frozen configuration value schema version on immutable rows."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260924_0003"
down_revision = "20260924_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing A01 validation rows have only the initial schema contract.
    op.add_column(
        "plt_configuration_versions",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema="plm",
    )
    op.create_check_constraint(
        "ck_plt_configuration_versions__schema_version",
        "plt_configuration_versions",
        "schema_version > 0",
        schema="plm",
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: configuration data must be checked")
    bind = op.get_bind()
    noninitial = bind.scalar(
        sa.text("SELECT count(*) FROM plm.plt_configuration_versions WHERE schema_version <> 1")
    )
    if noninitial:
        raise RuntimeError("noninitial configuration schema versions exist; downgrade refused")
    op.drop_constraint(
        "ck_plt_configuration_versions__schema_version",
        "plt_configuration_versions",
        schema="plm",
        type_="check",
    )
    op.drop_column("plt_configuration_versions", "schema_version", schema="plm")
