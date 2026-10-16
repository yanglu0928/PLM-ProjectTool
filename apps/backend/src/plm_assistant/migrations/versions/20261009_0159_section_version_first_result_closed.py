"""Add closed immutable first SectionVersion CREATE result storage.

Revision ID: 20261009_0159
Revises: 20261009_0158
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0159"
down_revision = "20261009_0158"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_section_version_create_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SolutionSectionVersion create result Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_solution_section_version_create_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SolutionSectionVersion create result history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_section_version_create_results",
        sa.Column("solution_section_version_id", ident, primary_key=True),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_document_version_ref", ident),
        sa.Column("content_artifact_ref", ident),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(), nullable=False),
        sa.Column("exclusions", postgresql.JSONB(), nullable=False),
        sa.Column("declared_requirement_count", sa.Integer(), nullable=False),
        sa.Column("declared_evidence_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_sol_section_version_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_section_version_results__actor", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_sol_section_version_results__number"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 500 AND title=btrim(title)",
                           name="ck_sol_section_version_results__title"),
        sa.CheckConstraint("(content_document_version_ref IS NULL) <> (content_artifact_ref IS NULL)",
                           name="ck_sol_section_version_results__content_xor"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_sol_section_version_results__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(assumptions)='array' AND jsonb_typeof(exclusions)='array'",
                           name="ck_sol_section_version_results__declarations"),
        sa.CheckConstraint("declared_requirement_count BETWEEN 0 AND 500 AND "
                           "declared_evidence_count BETWEEN 0 AND 500",
                           name="ck_sol_section_version_results__counts"),
        sa.CheckConstraint("supersedes_version_ref IS NULL OR "
                           "supersedes_version_ref<>solution_section_version_id",
                           name="ck_sol_section_version_results__supersedes_not_self"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_section_version_results__created_at"),
        schema="plm",
    )
    op.execute(_GUARDS)
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_section_version_create_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_version_create_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_section_version_create_result()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_section_version_create_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_section_version_create_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_section_version_create_result_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SectionVersion create result downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_version_create_results)"
    )).scalar_one():
        raise RuntimeError("SectionVersion create result history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_section_version_create_results__owner "
               "ON plm.sol_section_version_create_results")
    op.execute("DROP TRIGGER trg_sol_section_version_create_results__no_truncate "
               "ON plm.sol_section_version_create_results")
    op.drop_table("sol_section_version_create_results", schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_section_version_create_result()")
    op.execute("DROP FUNCTION plm.reject_solution_section_version_create_result_truncate()")
