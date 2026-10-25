"""Closed immutable first-success snapshot storage for SOL_SECTION_CREATE.

Revision ID: 20261009_0147
Revises: 20261009_0146
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0147"
down_revision = "20261009_0146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_section_create_results",
        sa.Column("solution_section_id", ident, primary_key=True),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False),
        sa.ForeignKeyConstraint(
            ["solution_section_id", "solution_outline_id", "project_id"],
            ["plm.sol_sections.solution_section_id",
             "plm.sol_sections.solution_outline_id", "plm.sol_sections.project_id"],
            name="fk_sol_section_create_results__section", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("char_length(section_key) BETWEEN 1 AND 128 AND "
                           "section_key=btrim(section_key)",
                           name="ck_sol_section_create_results__key"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_section_create_results__created_at"),
        schema="plm",
    )
    # The 0146 identity Guard still rejects both Section and result INSERT.
    # Do not open either until an authorized Owner + closure migration ship together.
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_section_create_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_create_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_identity_foundation()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_section_create_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_section_create_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_identity_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SolutionSection result downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_create_results)"
    )).scalar_one():
        raise RuntimeError("SolutionSection create result history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_section_create_results__owner "
               "ON plm.sol_section_create_results")
    op.execute("DROP TRIGGER trg_sol_section_create_results__no_truncate "
               "ON plm.sol_section_create_results")
    op.drop_table("sol_section_create_results", schema="plm")
