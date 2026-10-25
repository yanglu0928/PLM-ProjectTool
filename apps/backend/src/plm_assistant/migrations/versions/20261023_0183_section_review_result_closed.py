"""Add closed Section Review lifecycle result history; no state writer yet.

Revision ID: 20261023_0183
Revises: 20261023_0182
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261023_0183"
down_revision = "20261023_0182"
branch_labels = None
depends_on = None


_CLOSED = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_review_state_result_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Section Review result Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_section_review_state_results",
        sa.Column("review_state_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_section_version_id", ident, nullable=False),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("review_id", ident, nullable=False),
        sa.Column("review_round_id", ident, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("previous_approved_version_ref", ident),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(
            timezone=True, precision=6), nullable=False,
            server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint(
            "solution_section_version_id", "event_type",
            name="uq_sol_section_review_results__version_event"),
        sa.UniqueConstraint(
            "review_id", "review_round_id", "event_type",
            name="uq_sol_section_review_results__round_event"),
        sa.ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_sol_section_review_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["previous_approved_version_ref", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_sol_section_review_results__previous", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["current_approved_version_ref", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_sol_section_review_results__current", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_id"], ["plm.rvw_reviews.review_id"],
                                name="fk_sol_section_review_results__review",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_sol_section_review_results__round",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_sol_section_review_results__actor",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("event_type IN ('START','APPROVED','RETURNED','WITHDRAWN')",
                           name="ck_sol_section_review_results__event"),
        sa.CheckConstraint(
            "(event_type='APPROVED' AND "
            "current_approved_version_ref=solution_section_version_id) OR "
            "(event_type<>'APPROVED' AND current_approved_version_ref "
            "IS NOT DISTINCT FROM previous_approved_version_ref)",
            name="ck_sol_section_review_results__pointer"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_section_review_results__created_at"),
        schema="plm")
    op.create_index(
        "ix_sol_section_review_results__review_round",
        "sol_section_review_state_results", ["review_id", "review_round_id"],
        schema="plm")
    op.execute(_CLOSED)
    op.execute(
        "CREATE TRIGGER trg_sol_section_review_results__closed "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_review_state_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_section_review_state_result_closed()")
    op.execute(
        "CREATE TRIGGER trg_sol_section_review_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_section_review_state_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_section_review_state_result_closed()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Section Review result downgrade is disabled")
    op.execute("LOCK TABLE plm.sol_section_review_state_results IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_review_state_results)"
    )).scalar_one():
        raise RuntimeError("Section Review result history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_section_review_results__closed "
               "ON plm.sol_section_review_state_results")
    op.execute("DROP TRIGGER trg_sol_section_review_results__no_truncate "
               "ON plm.sol_section_review_state_results")
    op.drop_index("ix_sol_section_review_results__review_round",
                  table_name="sol_section_review_state_results", schema="plm")
    op.drop_table("sol_section_review_state_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_section_review_state_result_closed()")
