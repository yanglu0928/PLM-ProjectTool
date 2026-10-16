"""Closed first-result storage for SOL_REFERENCE_REVISE.

Revision ID: 20261009_0149
Revises: 20261009_0148
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0149"
down_revision = "20261009_0148"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_reference_revise_results",
        sa.Column("reference_version_id", ident, primary_key=True),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident, nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("source_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["reference_version_id", "reference_solution_id", "scope"],
            ["plm.sol_reference_versions.reference_version_id",
             "plm.sol_reference_versions.reference_solution_id",
             "plm.sol_reference_versions.scope"],
            name="fk_sol_reference_revise_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["supersedes_version_ref", "reference_solution_id", "scope"],
            ["plm.sol_reference_versions.reference_version_id",
             "plm.sol_reference_versions.reference_solution_id",
             "plm.sol_reference_versions.scope"],
            name="fk_sol_reference_revise_results__supersedes", ondelete="NO ACTION"),
        sa.CheckConstraint("scope IN ('GLOBAL','PROJECT')", name="ck_sol_reference_revise_results__scope"),
        sa.CheckConstraint("version_no>=2", name="ck_sol_reference_revise_results__number"),
        sa.CheckConstraint("supersedes_version_ref<>reference_version_id",
                           name="ck_sol_reference_revise_results__not_self"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_sol_reference_revise_results__content_fingerprint"),
        sa.CheckConstraint("octet_length(source_fingerprint)=32",
                           name="ck_sol_reference_revise_results__source_fingerprint"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_sol_reference_revise_results__created_at"),
        schema="plm",
    )
    # 0144 still only permits new immutable Reference rows. The result and root
    # pointer remain closed until the authorized Owner and closure ship together.
    op.execute("""
CREATE FUNCTION plm.guard_solution_reference_revise_result_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ReferenceSolution revise result Owner is not installed';
END; $$;
""")
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_reference_revise_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_reference_revise_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_reference_revise_result_closed()"))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_reference_revise_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_reference_revise_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_reference_truncate()"))
    # 0144 allowed every Reference INSERT for initial creation. A second version
    # must stay closed until the Revise Owner can advance the root atomically.
    op.execute("""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF TG_TABLE_NAME = 'sol_reference_versions' THEN
      IF NEW.version_no > 1 THEN
        RAISE EXCEPTION 'ReferenceSolution revise Owner is not installed';
      END IF;
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ReferenceSolution history is immutable';
END; $$;
""")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference revise result downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_reference_revise_results)"
    )).scalar_one():
        raise RuntimeError("Reference revise result history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_reference_revise_results__owner "
               "ON plm.sol_reference_revise_results")
    op.execute("DROP TRIGGER trg_sol_reference_revise_results__no_truncate "
               "ON plm.sol_reference_revise_results")
    op.execute("DROP FUNCTION plm.guard_solution_reference_revise_result_closed()")
    op.drop_table("sol_reference_revise_results", schema="plm")
    op.execute("""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ReferenceSolution history is immutable';
END; $$;
""")
