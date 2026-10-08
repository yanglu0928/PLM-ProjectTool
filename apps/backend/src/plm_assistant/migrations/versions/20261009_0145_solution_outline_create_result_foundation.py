"""Add closed first-success snapshot storage for SolutionOutline CREATE.

Revision ID: 20261009_0145
Revises: 20261008_0144
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0145"
down_revision = "20261008_0144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_outline_create_results",
        sa.Column("solution_outline_id", ident, primary_key=True),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False),
        sa.ForeignKeyConstraint(
            ["solution_outline_id", "project_id"],
            ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
            name="fk_sol_outline_create_results__outline", ondelete="NO ACTION",
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                           name="ck_sol_outline_create_results__name"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_outline_create_results__created_at"),
        schema="plm",
    )
    # A02 installs storage only. Both root and result INSERT remain closed until
    # the authorized A03 Owner and its guard migration ship as one unit.
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_outline_create_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_outline_create_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_identity_foundation()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_outline_create_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_outline_create_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_identity_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SolutionOutline result downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outline_create_results)"
    )).scalar_one():
        raise RuntimeError("SolutionOutline create result history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_outline_create_results__owner "
               "ON plm.sol_outline_create_results")
    op.execute("DROP TRIGGER trg_sol_outline_create_results__no_truncate "
               "ON plm.sol_outline_create_results")
    op.drop_table("sol_outline_create_results", schema="plm")
