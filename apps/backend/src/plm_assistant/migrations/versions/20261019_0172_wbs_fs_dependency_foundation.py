"""Add closed PLN-02 same-version FS WBS dependencies.

Revision ID: 20261019_0172
Revises: 20261019_0171
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0172"
down_revision = "20261019_0171"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_wbs_dependency_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsDependency Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_wbs_dependency_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsDependency history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "pln_wbs_dependencies",
        sa.Column("dependency_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("predecessor_item_id", ident, nullable=False),
        sa.Column("successor_item_id", ident, nullable=False),
        sa.Column("dependency_type", sa.Text(), nullable=False,
                  server_default=sa.text("'FS'")),
        sa.Column("lag", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lag_unit", sa.Text()),
        sa.Column("lag_reason", sa.Text()),
        sa.UniqueConstraint("plan_version_id", "predecessor_item_id", "successor_item_id",
                            name="uq_pln_wbs_deps__version_edge"),
        sa.ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_wbs_deps__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["predecessor_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_deps__predecessor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["successor_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_deps__successor", ondelete="NO ACTION"),
        sa.CheckConstraint("dependency_type='FS'", name="ck_pln_wbs_deps__type"),
        sa.CheckConstraint("predecessor_item_id<>successor_item_id",
                           name="ck_pln_wbs_deps__not_self"),
        sa.CheckConstraint("lag_unit IS NULL OR (char_length(lag_unit) BETWEEN 1 AND 32 "
                           "AND lag_unit=btrim(lag_unit))", name="ck_pln_wbs_deps__lag_unit"),
        sa.CheckConstraint("lag_reason IS NULL OR (char_length(lag_reason) BETWEEN 1 AND 1000 "
                           "AND lag_reason=btrim(lag_reason))", name="ck_pln_wbs_deps__lag_reason"),
        sa.CheckConstraint("lag=0 OR (lag_unit IS NOT NULL AND lag_reason IS NOT NULL)",
                           name="ck_pln_wbs_deps__lag_explicit"),
        schema="plm",
    )
    op.create_index("ix_pln_wbs_deps__out", "pln_wbs_dependencies",
                    ["plan_version_id", "predecessor_item_id", "successor_item_id"], schema="plm")
    op.create_index("ix_pln_wbs_deps__in", "pln_wbs_dependencies",
                    ["plan_version_id", "successor_item_id", "predecessor_item_id"], schema="plm")
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_wbs_dependencies__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_wbs_dependencies FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_wbs_dependency_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_wbs_dependencies__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_wbs_dependencies FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_wbs_dependency_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline WbsDependency downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_wbs_dependencies)"
    )).scalar_one():
        raise RuntimeError("WbsDependency history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_wbs_dependencies__owner ON plm.pln_wbs_dependencies")
    op.execute("DROP TRIGGER trg_pln_wbs_dependencies__no_truncate ON plm.pln_wbs_dependencies")
    op.drop_index("ix_pln_wbs_deps__in", table_name="pln_wbs_dependencies", schema="plm")
    op.drop_index("ix_pln_wbs_deps__out", table_name="pln_wbs_dependencies", schema="plm")
    op.drop_table("pln_wbs_dependencies", schema="plm")
    op.execute("DROP FUNCTION plm.guard_wbs_dependency_foundation()")
    op.execute("DROP FUNCTION plm.reject_wbs_dependency_truncate()")
