"""Add normalized fields required by the frozen PlanVersion snapshot.

Revision ID: 20261026_0186
Revises: 20261024_0185
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261026_0186"
down_revision = "20261024_0185"
branch_labels = None
depends_on = None


_TABLES = (
    "pln_version_exclusions", "pln_wbs_support_roles", "pln_wbs_conditions",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_plan_snapshot_child_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan snapshot Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plan_snapshot_child_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plan snapshot history cannot be truncated';
END; $$;
"""


def _install_closed_guards(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
        f"ON plm.{table} FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_snapshot_child_foundation()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
        f"ON plm.{table} FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_plan_snapshot_child_truncate()"
    )


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.add_column("pln_plan_versions", sa.Column("calendar_ref", sa.Text()), schema="plm")
    op.create_check_constraint(
        "ck_pln_plan_versions__calendar_ref", "pln_plan_versions",
        "calendar_ref IS NULL OR (char_length(calendar_ref) BETWEEN 1 AND 128 "
        "AND calendar_ref=btrim(calendar_ref) AND calendar_ref ~ '^[A-Z][A-Z0-9_]*$')",
        schema="plm",
    )

    for name, type_ in (
        ("category_code", sa.Text()),
        ("owner_project_member_id", ident),
        ("planned_start_date", sa.Date()),
        ("planned_finish_date", sa.Date()),
        ("planned_duration_minutes", sa.Integer()),
        ("actual_start_date", sa.Date()),
        ("actual_finish_date", sa.Date()),
        ("risk_summary", sa.Text()),
        ("explicit_exclusion_reason", sa.Text()),
    ):
        op.add_column("pln_wbs_items", sa.Column(name, type_), schema="plm")
    op.create_foreign_key(
        "fk_pln_wbs_items__owner_member", "pln_wbs_items", "prj_project_members",
        ["owner_project_member_id", "project_id"], ["project_member_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
    )
    checks = (
        ("ck_pln_wbs_items__category", "category_code IS NULL OR "
         "(char_length(category_code) BETWEEN 1 AND 64 AND category_code=btrim(category_code) "
         "AND category_code ~ '^[A-Z][A-Z0-9_]*$')"),
        ("ck_pln_wbs_items__planned_duration",
         "planned_duration_minutes IS NULL OR planned_duration_minutes>=0"),
        ("ck_pln_wbs_items__planned_date_pair",
         "(planned_start_date IS NULL)=(planned_finish_date IS NULL)"),
        ("ck_pln_wbs_items__planned_date_order",
         "planned_finish_date IS NULL OR planned_finish_date>=planned_start_date"),
        ("ck_pln_wbs_items__actual_date_pair",
         "(actual_start_date IS NULL)=(actual_finish_date IS NULL)"),
        ("ck_pln_wbs_items__actual_date_order",
         "actual_finish_date IS NULL OR actual_finish_date>=actual_start_date"),
        ("ck_pln_wbs_items__risk_summary", "risk_summary IS NULL OR "
         "(char_length(risk_summary) BETWEEN 1 AND 2000 AND risk_summary=btrim(risk_summary))"),
        ("ck_pln_wbs_items__exclusion_reason", "explicit_exclusion_reason IS NULL OR "
         "(char_length(explicit_exclusion_reason) BETWEEN 1 AND 2000 "
         "AND explicit_exclusion_reason=btrim(explicit_exclusion_reason))"),
    )
    for name, expression in checks:
        op.create_check_constraint(name, "pln_wbs_items", expression, schema="plm")

    op.create_table(
        "pln_wbs_support_roles",
        sa.Column("support_role_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("wbs_item_id", ident, nullable=False),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("support_role", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("wbs_item_id", "support_role",
                            name="uq_pln_wbs_support_roles__item_role"),
        sa.UniqueConstraint("wbs_item_id", "ordinal",
                            name="uq_pln_wbs_support_roles__item_ordinal"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_support_roles__item", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "char_length(support_role) BETWEEN 1 AND 64 AND support_role=btrim(support_role) "
            "AND support_role ~ '^[A-Z][A-Z0-9_]*$'",
            name="ck_pln_wbs_support_roles__role"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_wbs_support_roles__ordinal"),
        schema="plm",
    )
    op.create_index("ix_pln_wbs_support_roles__project_version",
                    "pln_wbs_support_roles", ["project_id", "plan_version_id"], schema="plm")

    op.create_table(
        "pln_wbs_conditions",
        sa.Column("condition_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("wbs_item_id", ident, nullable=False),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("condition_kind", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("condition_text", sa.Text(), nullable=False),
        sa.UniqueConstraint("wbs_item_id", "condition_kind", "ordinal",
                            name="uq_pln_wbs_conditions__item_kind_ordinal"),
        sa.ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_conditions__item", ondelete="NO ACTION"),
        sa.CheckConstraint("condition_kind IN ('ENTRY','ACCEPTANCE')",
                           name="ck_pln_wbs_conditions__kind"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_wbs_conditions__ordinal"),
        sa.CheckConstraint("char_length(condition_text) BETWEEN 1 AND 2000 "
                           "AND condition_text=btrim(condition_text)",
                           name="ck_pln_wbs_conditions__text"),
        schema="plm",
    )
    op.create_index("ix_pln_wbs_conditions__project_version", "pln_wbs_conditions",
                    ["project_id", "plan_version_id"], schema="plm")

    op.create_table(
        "pln_version_exclusions",
        sa.Column("exclusion_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plan_version_id", ident, nullable=False),
        sa.Column("plan_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("requirement_id", ident),
        sa.Column("requirement_version_id", ident),
        sa.Column("solution_outline_id", ident),
        sa.Column("solution_outline_version_id", ident),
        sa.Column("solution_section_id", ident),
        sa.Column("solution_section_version_id", ident),
        sa.Column("spec_series_id", ident),
        sa.Column("structured_solution_spec_id", ident),
        sa.Column("spec_type", sa.Text()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.UniqueConstraint("exclusion_id", "plan_version_id", "plan_id", "project_id",
                            name="uq_pln_version_exclusions__id_version_plan_project"),
        sa.UniqueConstraint("plan_version_id", "ordinal",
                            name="uq_pln_version_exclusions__version_ordinal"),
        sa.UniqueConstraint("plan_version_id", "requirement_version_id",
                            name="uq_pln_version_exclusions__requirement"),
        sa.UniqueConstraint("plan_version_id", "solution_outline_version_id",
                            name="uq_pln_version_exclusions__outline"),
        sa.UniqueConstraint("plan_version_id", "solution_section_version_id",
                            name="uq_pln_version_exclusions__section"),
        sa.UniqueConstraint("plan_version_id", "structured_solution_spec_id",
                            name="uq_pln_version_exclusions__spec"),
        sa.ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_version_exclusions__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_pln_version_exclusions__requirement", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["solution_outline_version_id", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_pln_version_exclusions__outline", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_pln_version_exclusions__section", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id", "spec_type"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id", "plm.sol_structured_specs.project_id",
             "plm.sol_structured_specs.spec_type"],
            name="fk_pln_version_exclusions__spec", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_pln_version_exclusions__ordinal"),
        sa.CheckConstraint(
            "target_kind IN ('REQUIREMENT_VERSION','SOLUTION_OUTLINE_VERSION',"
            "'SOLUTION_SECTION_VERSION','STRUCTURED_SPEC_VERSION')",
            name="ck_pln_version_exclusions__kind"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
                           name="ck_pln_version_exclusions__reason"),
        sa.CheckConstraint("char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
                           name="ck_pln_version_exclusions__impact"),
        sa.CheckConstraint(
            "(target_kind='REQUIREMENT_VERSION' AND requirement_id IS NOT NULL "
            "AND requirement_version_id IS NOT NULL AND solution_outline_id IS NULL "
            "AND solution_outline_version_id IS NULL AND solution_section_id IS NULL "
            "AND solution_section_version_id IS NULL AND spec_series_id IS NULL "
            "AND structured_solution_spec_id IS NULL AND spec_type IS NULL) OR "
            "(target_kind='SOLUTION_OUTLINE_VERSION' AND requirement_id IS NULL "
            "AND requirement_version_id IS NULL AND solution_outline_id IS NOT NULL "
            "AND solution_outline_version_id IS NOT NULL AND solution_section_id IS NULL "
            "AND solution_section_version_id IS NULL AND spec_series_id IS NULL "
            "AND structured_solution_spec_id IS NULL AND spec_type IS NULL) OR "
            "(target_kind='SOLUTION_SECTION_VERSION' AND requirement_id IS NULL "
            "AND requirement_version_id IS NULL AND solution_outline_id IS NULL "
            "AND solution_outline_version_id IS NULL AND solution_section_id IS NOT NULL "
            "AND solution_section_version_id IS NOT NULL AND spec_series_id IS NULL "
            "AND structured_solution_spec_id IS NULL AND spec_type IS NULL) OR "
            "(target_kind='STRUCTURED_SPEC_VERSION' AND requirement_id IS NULL "
            "AND requirement_version_id IS NULL AND solution_outline_id IS NULL "
            "AND solution_outline_version_id IS NULL AND solution_section_id IS NULL "
            "AND solution_section_version_id IS NULL AND spec_series_id IS NOT NULL "
            "AND structured_solution_spec_id IS NOT NULL AND spec_type IS NOT NULL)",
            name="ck_pln_version_exclusions__typed_target"),
        schema="plm",
    )
    op.create_index("ix_pln_version_exclusions__target", "pln_version_exclusions",
                    ["project_id", "target_kind", "plan_version_id"], schema="plm")

    op.execute(_GUARDS)
    for table in _TABLES:
        _install_closed_guards(table)


def _has_snapshot_history() -> bool:
    bind = op.get_bind()
    return bool(bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.pln_version_exclusions) "
        "OR EXISTS (SELECT 1 FROM plm.pln_wbs_support_roles) "
        "OR EXISTS (SELECT 1 FROM plm.pln_wbs_conditions) "
        "OR EXISTS (SELECT 1 FROM plm.pln_plan_versions WHERE calendar_ref IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM plm.pln_wbs_items WHERE category_code IS NOT NULL "
        "OR owner_project_member_id IS NOT NULL OR planned_start_date IS NOT NULL "
        "OR planned_finish_date IS NOT NULL OR planned_duration_minutes IS NOT NULL "
        "OR actual_start_date IS NOT NULL OR actual_finish_date IS NOT NULL "
        "OR risk_summary IS NOT NULL OR explicit_exclusion_reason IS NOT NULL)"
    )).scalar_one())


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PlanVersion snapshot downgrade is disabled")
    if _has_snapshot_history():
        raise RuntimeError("PlanVersion snapshot history prevents downgrade")
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    for table, index in (
        ("pln_version_exclusions", "ix_pln_version_exclusions__target"),
        ("pln_wbs_support_roles", "ix_pln_wbs_support_roles__project_version"),
        ("pln_wbs_conditions", "ix_pln_wbs_conditions__project_version"),
    ):
        op.drop_index(index, table_name=table, schema="plm")
    for table in _TABLES:
        op.drop_table(table, schema="plm")

    for name in (
        "ck_pln_wbs_items__exclusion_reason", "ck_pln_wbs_items__risk_summary",
        "ck_pln_wbs_items__actual_date_order", "ck_pln_wbs_items__actual_date_pair",
        "ck_pln_wbs_items__planned_date_order", "ck_pln_wbs_items__planned_date_pair",
        "ck_pln_wbs_items__planned_duration", "ck_pln_wbs_items__category",
    ):
        op.drop_constraint(name, "pln_wbs_items", schema="plm", type_="check")
    op.drop_constraint("fk_pln_wbs_items__owner_member", "pln_wbs_items",
                       schema="plm", type_="foreignkey")
    for name in (
        "explicit_exclusion_reason", "risk_summary", "actual_finish_date",
        "actual_start_date", "planned_duration_minutes", "planned_finish_date",
        "planned_start_date", "owner_project_member_id", "category_code",
    ):
        op.drop_column("pln_wbs_items", name, schema="plm")
    op.drop_constraint("ck_pln_plan_versions__calendar_ref", "pln_plan_versions",
                       schema="plm", type_="check")
    op.drop_column("pln_plan_versions", "calendar_ref", schema="plm")
    op.execute("DROP FUNCTION plm.guard_plan_snapshot_child_foundation()")
    op.execute("DROP FUNCTION plm.reject_plan_snapshot_child_truncate()")
