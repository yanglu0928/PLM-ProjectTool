"""Add closed immutable first PLAN_CREATE response snapshot.

Revision ID: 20261019_0168
Revises: 20261019_0167
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0168"
down_revision = "20261019_0167"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan create result Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plan_create_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan create result history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "pln_plan_create_results",
        sa.Column("plan_id", ident, primary_key=True),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["plan_id", "project_id"],
                                ["plm.pln_plans.plan_id", "plm.pln_plans.project_id"],
                                name="fk_pln_plan_create_results__plan", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                           name="ck_pln_plan_create_results__name"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_pln_plan_create_results__created_at"),
        schema="plm",
    )
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_plan_create_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.pln_plan_create_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_plan_create_result()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_plan_create_results__no_truncate "
        "BEFORE TRUNCATE ON plm.pln_plan_create_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plan_create_result_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plan create result downgrade is disabled")
    if op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm.pln_plan_create_results)"
    )).scalar_one():
        raise RuntimeError("Plan create result history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_plan_create_results__owner ON plm.pln_plan_create_results")
    op.execute("DROP TRIGGER trg_pln_plan_create_results__no_truncate ON plm.pln_plan_create_results")
    op.drop_table("pln_plan_create_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_plan_create_result()")
    op.execute("DROP FUNCTION plm.reject_plan_create_result_truncate()")
