"""Add closed, explicit SectionVersion Spec declaration and fixed references.

Revision ID: 20261023_0178
Revises: 20261019_0177
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261023_0178"
down_revision = "20261019_0177"
branch_labels = None
depends_on = None


_ROOT_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_binding_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND NEW.spec_binding_state='UNDECLARED'
     AND NEW.declared_spec_count=0 AND NEW.spec_not_required_reason IS NULL THEN
    RETURN NEW;
  END IF;
  IF TG_OP='UPDATE'
     AND NEW.spec_binding_state IS NOT DISTINCT FROM OLD.spec_binding_state
     AND NEW.declared_spec_count IS NOT DISTINCT FROM OLD.declared_spec_count
     AND NEW.spec_not_required_reason IS NOT DISTINCT FROM OLD.spec_not_required_reason THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'SectionVersion Spec binding Owner is not installed';
END; $$;
"""

_CHILD_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_spec_refs_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SectionVersion SpecRef Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.add_column("sol_section_versions", sa.Column(
        "spec_binding_state", sa.Text(), nullable=False,
        server_default=sa.text("'UNDECLARED'")), schema="plm")
    op.add_column("sol_section_versions", sa.Column(
        "spec_not_required_reason", sa.Text()), schema="plm")
    op.add_column("sol_section_versions", sa.Column(
        "declared_spec_count", sa.Integer(), nullable=False,
        server_default=sa.text("0")), schema="plm")
    op.create_check_constraint(
        "ck_sol_section_versions__spec_binding", "sol_section_versions",
        "(spec_binding_state='UNDECLARED' AND declared_spec_count=0 "
        "AND spec_not_required_reason IS NULL) OR "
        "(spec_binding_state='NONE_REQUIRED' AND declared_spec_count=0 "
        "AND spec_not_required_reason IS NOT NULL "
        "AND char_length(spec_not_required_reason) BETWEEN 1 AND 1000 "
        "AND spec_not_required_reason=btrim(spec_not_required_reason)) OR "
        "(spec_binding_state='FIXED_REFS' AND declared_spec_count BETWEEN 1 AND 500 "
        "AND spec_not_required_reason IS NULL)", schema="plm")

    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_section_spec_refs",
        sa.Column("solution_section_spec_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_section_version_id", ident, nullable=False),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("spec_series_id", ident, nullable=False),
        sa.Column("structured_solution_spec_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("solution_section_version_id", "ordinal",
                            name="uq_sol_section_specs__version_ordinal"),
        sa.UniqueConstraint("solution_section_version_id", "spec_series_id",
                            name="uq_sol_section_specs__version_series"),
        sa.ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_sol_section_specs__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id"],
            name="fk_sol_section_specs__spec", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_section_specs__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_section_specs__target", "sol_section_spec_refs",
                    ["structured_solution_spec_id", "solution_section_version_id"],
                    schema="plm")
    op.execute(_ROOT_GUARD)
    op.execute(_CHILD_GUARD)
    op.execute(
        "CREATE TRIGGER trg_sol_section_versions__spec_binding "
        "BEFORE INSERT OR UPDATE ON plm.sol_section_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_section_spec_binding_closed()")
    op.execute(
        "CREATE TRIGGER trg_sol_section_spec_refs__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_spec_refs "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_section_spec_refs_closed()")
    op.execute(
        "CREATE TRIGGER trg_sol_section_spec_refs__truncate "
        "BEFORE TRUNCATE ON plm.sol_section_spec_refs "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_section_spec_refs_closed()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SectionVersion Spec binding downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_versions "
        "WHERE spec_binding_state<>'UNDECLARED' OR declared_spec_count<>0 "
        "OR spec_not_required_reason IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM plm.sol_section_spec_refs)"
    )).scalar_one():
        raise RuntimeError("SectionVersion Spec binding history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_section_spec_refs__truncate ON plm.sol_section_spec_refs")
    op.execute("DROP TRIGGER trg_sol_section_spec_refs__owner ON plm.sol_section_spec_refs")
    op.execute("DROP TRIGGER trg_sol_section_versions__spec_binding ON plm.sol_section_versions")
    op.execute("DROP FUNCTION plm.guard_section_spec_refs_closed()")
    op.execute("DROP FUNCTION plm.guard_section_spec_binding_closed()")
    op.drop_index("ix_sol_section_specs__target", table_name="sol_section_spec_refs",
                  schema="plm")
    op.drop_table("sol_section_spec_refs", schema="plm")
    op.drop_constraint("ck_sol_section_versions__spec_binding", "sol_section_versions",
                       schema="plm", type_="check")
    op.drop_column("sol_section_versions", "declared_spec_count", schema="plm")
    op.drop_column("sol_section_versions", "spec_not_required_reason", schema="plm")
    op.drop_column("sol_section_versions", "spec_binding_state", schema="plm")
