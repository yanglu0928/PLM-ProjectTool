"""Add closed PLN-02 milestones and same-version WBS links.

Revision ID: 20261019_0173
Revises: 20261019_0172
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0173"
down_revision = "20261019_0172"
branch_labels = None
depends_on = None

_TABLES = ("pln_milestones", "pln_milestone_item_refs")
_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_milestone_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PlanMilestone Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plan_milestone_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PlanMilestone history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "pln_milestones",
        sa.Column("milestone_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("acceptance_rule", sa.Text(), nullable=False),
        sa.Column("gate_ref", sa.Text()),
        sa.Column("milestone_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PLANNED'")),
        sa.UniqueConstraint("milestone_id", "plan_version_id", "plan_id", "project_id",
                            name="uq_pln_milestones__id_version_plan_project"),
        sa.UniqueConstraint("plan_version_id", "name",
                            name="uq_pln_milestones__version_name"),
        sa.ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_milestones__version", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                           name="ck_pln_milestones__name"),
        sa.CheckConstraint("isfinite(target_date)", name="ck_pln_milestones__target_date"),
        sa.CheckConstraint("duration_days>=0", name="ck_pln_milestones__duration"),
        sa.CheckConstraint("char_length(acceptance_rule) BETWEEN 1 AND 2000 "
                           "AND acceptance_rule=btrim(acceptance_rule)",
                           name="ck_pln_milestones__acceptance"),
        sa.CheckConstraint("gate_ref IS NULL OR (char_length(gate_ref) BETWEEN 1 AND 128 "
                           "AND gate_ref=btrim(gate_ref))", name="ck_pln_milestones__gate_ref"),
        sa.CheckConstraint("milestone_state IN ('PLANNED','ACHIEVED','CANCELLED')",
                           name="ck_pln_milestones__state"),
        schema="plm",
    )
    op.create_index("ix_pln_milestones__version_target", "pln_milestones",
                    ["plan_version_id", "target_date", "milestone_id"], schema="plm")
    op.create_table(
        "pln_milestone_item_refs",
        sa.Column("milestone_item_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("milestone_id", ident, nullable=False),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("wbs_item_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("milestone_id", "wbs_item_id",
                            name="uq_pln_milestone_items__milestone_item"),
        sa.UniqueConstraint("milestone_id", "ordinal",
                            name="uq_pln_milestone_items__milestone_ordinal"),
        sa.ForeignKeyConstraint(
            ["milestone_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_milestones.milestone_id", "plm.pln_milestones.plan_version_id",
             "plm.pln_milestones.plan_id", "plm.pln_milestones.project_id"],
            name="fk_pln_milestone_items__milestone", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_milestone_items__wbs", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_milestone_items__ordinal"),
        schema="plm",
    )
    op.create_index("ix_pln_milestone_items__wbs", "pln_milestone_item_refs",
                    ["plan_version_id", "wbs_item_id", "milestone_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_plan_milestone_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT "
            f"EXECUTE FUNCTION plm.reject_plan_milestone_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PlanMilestone downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("PlanMilestone history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
    op.drop_index("ix_pln_milestone_items__wbs", table_name="pln_milestone_item_refs",
                  schema="plm")
    op.drop_table("pln_milestone_item_refs", schema="plm")
    op.drop_index("ix_pln_milestones__version_target", table_name="pln_milestones",
                  schema="plm")
    op.drop_table("pln_milestones", schema="plm")
    op.execute("DROP FUNCTION plm.guard_plan_milestone_foundation()")
    op.execute("DROP FUNCTION plm.reject_plan_milestone_truncate()")
