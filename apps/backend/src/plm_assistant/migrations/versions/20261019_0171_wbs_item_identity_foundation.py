"""Add closed version-scoped WBS item identity and hierarchy.

Revision ID: 20261019_0171
Revises: 20261019_0170
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0171"
down_revision = "20261019_0170"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_wbs_item_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsItem Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_wbs_item_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsItem history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "pln_wbs_items",
        sa.Column("wbs_item_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("parent_item_id", ident),
        sa.Column("wbs_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("item_state", sa.Text(), nullable=False,
                  server_default=sa.text("'NOT_STARTED'")),
        sa.UniqueConstraint("wbs_item_id", "plan_version_id", "plan_id", "project_id",
                            name="uq_pln_wbs_items__id_version_plan_project"),
        sa.UniqueConstraint("plan_version_id", "wbs_code",
                            name="uq_pln_wbs_items__version_code"),
        sa.UniqueConstraint("plan_version_id", "parent_item_id", "ordinal",
                            name="uq_pln_wbs_items__parent_ordinal",
                            postgresql_nulls_not_distinct=True),
        sa.ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_wbs_items__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["parent_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_items__parent", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("char_length(wbs_code) BETWEEN 1 AND 64 AND wbs_code=btrim(wbs_code)",
                           name="ck_pln_wbs_items__code"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                           name="ck_pln_wbs_items__name"),
        sa.CheckConstraint("(parent_item_id IS NULL AND level=1) OR "
                           "(parent_item_id IS NOT NULL AND level BETWEEN 2 AND 6)",
                           name="ck_pln_wbs_items__level_root"),
        sa.CheckConstraint("parent_item_id IS NULL OR parent_item_id<>wbs_item_id",
                           name="ck_pln_wbs_items__not_self"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_wbs_items__ordinal"),
        sa.CheckConstraint("item_state IN "
                           "('NOT_STARTED','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED')",
                           name="ck_pln_wbs_items__state"),
        schema="plm",
    )
    op.create_index("ix_pln_wbs_items__parent_order", "pln_wbs_items",
                    ["plan_version_id", "parent_item_id", "ordinal", "wbs_item_id"],
                    schema="plm")
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_wbs_items__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_wbs_items FOR EACH ROW EXECUTE FUNCTION plm.guard_wbs_item_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_wbs_items__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_wbs_items FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_wbs_item_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline WbsItem downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_wbs_items)"
    )).scalar_one():
        raise RuntimeError("WbsItem history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_wbs_items__owner ON plm.pln_wbs_items")
    op.execute("DROP TRIGGER trg_pln_wbs_items__no_truncate ON plm.pln_wbs_items")
    op.drop_index("ix_pln_wbs_items__parent_order", table_name="pln_wbs_items", schema="plm")
    op.drop_table("pln_wbs_items", schema="plm")
    op.execute("DROP FUNCTION plm.guard_wbs_item_foundation()")
    op.execute("DROP FUNCTION plm.reject_wbs_item_truncate()")
