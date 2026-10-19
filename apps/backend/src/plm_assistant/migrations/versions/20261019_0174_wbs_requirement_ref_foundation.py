"""Add closed WBS to fixed RequirementVersion references.

Revision ID: 20261019_0174
Revises: 20261019_0173
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0174"
down_revision = "20261019_0173"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_wbs_requirement_ref_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsRequirementRef Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_wbs_requirement_ref_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsRequirementRef history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "pln_item_requirement_refs",
        sa.Column("item_requirement_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("wbs_item_id", ident, nullable=False),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("wbs_item_id", "requirement_version_id",
                            name="uq_pln_item_requirements__item_version"),
        sa.UniqueConstraint("wbs_item_id", "ordinal",
                            name="uq_pln_item_requirements__item_ordinal"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_requirements__wbs", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_pln_item_requirements__requirement", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_item_requirements__ordinal"),
        schema="plm",
    )
    op.create_index("ix_pln_item_requirements__target", "pln_item_requirement_refs",
                    ["project_id", "requirement_version_id", "plan_version_id"], schema="plm")
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_item_requirement_refs__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_item_requirement_refs FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_wbs_requirement_ref_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_item_requirement_refs__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_item_requirement_refs FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_wbs_requirement_ref_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline WbsRequirementRef downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_item_requirement_refs)"
    )).scalar_one():
        raise RuntimeError("WbsRequirementRef history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_item_requirement_refs__owner "
               "ON plm.pln_item_requirement_refs")
    op.execute("DROP TRIGGER trg_pln_item_requirement_refs__no_truncate "
               "ON plm.pln_item_requirement_refs")
    op.drop_index("ix_pln_item_requirements__target",
                  table_name="pln_item_requirement_refs", schema="plm")
    op.drop_table("pln_item_requirement_refs", schema="plm")
    op.execute("DROP FUNCTION plm.guard_wbs_requirement_ref_foundation()")
    op.execute("DROP FUNCTION plm.reject_wbs_requirement_ref_truncate()")
