"""Add closed typed WBS to fixed Solution-version references.

Revision ID: 20261019_0175
Revises: 20261019_0174
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0175"
down_revision = "20261019_0174"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_wbs_solution_ref_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsSolutionRef Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_wbs_solution_ref_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'WbsSolutionRef history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "pln_item_solution_refs",
        sa.Column("item_solution_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("wbs_item_id", ident, nullable=False),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("solution_outline_version_id", ident),
        sa.Column("solution_outline_id", ident),
        sa.Column("solution_section_version_id", ident),
        sa.Column("solution_section_id", ident),
        sa.Column("structured_solution_spec_id", ident),
        sa.Column("spec_series_id", ident),
        sa.Column("spec_type", sa.Text()),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("wbs_item_id", "ordinal",
                            name="uq_pln_item_solutions__item_ordinal"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_solutions__wbs", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["solution_outline_version_id", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_pln_item_solutions__outline", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_pln_item_solutions__section", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id", "spec_type"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id", "plm.sol_structured_specs.spec_type"],
            name="fk_pln_item_solutions__spec", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_item_solutions__ordinal"),
        sa.CheckConstraint(
            "(source_kind='OUTLINE' AND solution_outline_version_id IS NOT NULL "
            "AND solution_outline_id IS NOT NULL AND solution_section_version_id IS NULL "
            "AND solution_section_id IS NULL AND structured_solution_spec_id IS NULL "
            "AND spec_series_id IS NULL AND spec_type IS NULL) OR "
            "(source_kind='SECTION' AND solution_outline_version_id IS NULL "
            "AND solution_outline_id IS NULL AND solution_section_version_id IS NOT NULL "
            "AND solution_section_id IS NOT NULL AND structured_solution_spec_id IS NULL "
            "AND spec_series_id IS NULL AND spec_type IS NULL) OR "
            "(source_kind='STRUCTURED_SPEC' AND solution_outline_version_id IS NULL "
            "AND solution_outline_id IS NULL AND solution_section_version_id IS NULL "
            "AND solution_section_id IS NULL AND structured_solution_spec_id IS NOT NULL "
            "AND spec_series_id IS NOT NULL AND spec_type IS NOT NULL)",
            name="ck_pln_item_solutions__typed_target"),
        schema="plm",
    )
    for name, column, kind in (
        ("outline", "solution_outline_version_id", "OUTLINE"),
        ("section", "solution_section_version_id", "SECTION"),
        ("spec", "structured_solution_spec_id", "STRUCTURED_SPEC"),
    ):
        op.create_index(
            f"uq_pln_item_solutions__{name}", "pln_item_solution_refs",
            ["wbs_item_id", column], unique=True, schema="plm",
            postgresql_where=sa.text(f"source_kind='{kind}'"))
    op.create_index("ix_pln_item_solutions__project_kind", "pln_item_solution_refs",
                    ["project_id", "source_kind", "plan_version_id"], schema="plm")
    op.execute(_GUARDS)
    op.execute(
        "CREATE TRIGGER trg_pln_item_solution_refs__owner BEFORE INSERT OR UPDATE OR DELETE "
        "ON plm.pln_item_solution_refs FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_wbs_solution_ref_foundation()"
    )
    op.execute(
        "CREATE TRIGGER trg_pln_item_solution_refs__no_truncate BEFORE TRUNCATE "
        "ON plm.pln_item_solution_refs FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_wbs_solution_ref_truncate()"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline WbsSolutionRef downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_item_solution_refs)"
    )).scalar_one():
        raise RuntimeError("WbsSolutionRef history prevents downgrade")
    op.execute("DROP TRIGGER trg_pln_item_solution_refs__owner "
               "ON plm.pln_item_solution_refs")
    op.execute("DROP TRIGGER trg_pln_item_solution_refs__no_truncate "
               "ON plm.pln_item_solution_refs")
    op.drop_index("ix_pln_item_solutions__project_kind",
                  table_name="pln_item_solution_refs", schema="plm")
    for name in ("outline", "section", "spec"):
        op.drop_index(f"uq_pln_item_solutions__{name}",
                      table_name="pln_item_solution_refs", schema="plm")
    op.drop_table("pln_item_solution_refs", schema="plm")
    op.execute("DROP FUNCTION plm.guard_wbs_solution_ref_foundation()")
    op.execute("DROP FUNCTION plm.reject_wbs_solution_ref_truncate()")
