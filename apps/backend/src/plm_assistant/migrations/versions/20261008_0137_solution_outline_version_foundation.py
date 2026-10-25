"""Add closed SOL-03 OutlineVersion and fixed section/requirement references.

Revision ID: 20261008_0137
Revises: 20261008_0136
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0137"
down_revision = "20261008_0136"
branch_labels = None
depends_on = None

_TABLES = ("sol_outline_versions", "sol_outline_sections", "sol_outline_requirement_refs")
_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_outline_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SolutionOutlineVersion Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_solution_outline_version_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SolutionOutlineVersion history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_unique_constraint(
        "uq_sol_sections__id_outline_project", "sol_sections",
        ["solution_section_id", "solution_outline_id", "project_id"], schema="plm",
    )
    op.create_table(
        "sol_outline_versions",
        sa.Column("solution_outline_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("missing_declarations", postgresql.JSONB(), nullable=False),
        sa.Column("conflict_declarations", postgresql.JSONB(), nullable=False),
        sa.Column("declared_section_count", sa.Integer(), nullable=False),
        sa.Column("declared_requirement_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("solution_outline_version_id", "solution_outline_id", "project_id",
                            name="uq_sol_outline_versions__id_outline_project"),
        sa.UniqueConstraint("solution_outline_id", "version_no",
                            name="uq_sol_outline_versions__outline_no"),
        sa.ForeignKeyConstraint(["solution_outline_id", "project_id"],
                                ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
                                name="fk_sol_outline_versions__outline", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_ref", "solution_outline_id", "project_id"],
                                ["plm.sol_outline_versions.solution_outline_version_id",
                                 "plm.sol_outline_versions.solution_outline_id",
                                 "plm.sol_outline_versions.project_id"],
                                name="fk_sol_outline_versions__supersedes", ondelete="NO ACTION",
                                deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_sol_outline_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_sol_outline_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_outline_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_sol_outline_versions__number"),
        sa.CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
                           name="ck_sol_outline_versions__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_sol_outline_versions__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(missing_declarations)='array' AND "
                           "jsonb_typeof(conflict_declarations)='array'",
                           name="ck_sol_outline_versions__declarations"),
        sa.CheckConstraint("declared_section_count BETWEEN 0 AND 100 AND "
                           "declared_requirement_count BETWEEN 0 AND 500",
                           name="ck_sol_outline_versions__counts"),
        sa.CheckConstraint("supersedes_version_ref IS NULL OR "
                           "supersedes_version_ref<>solution_outline_version_id",
                           name="ck_sol_outline_versions__supersedes_not_self"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                           "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                           name="ck_sol_outline_versions__review_pair"),
        schema="plm",
    )
    op.create_index("ix_sol_outline_versions__outline_created", "sol_outline_versions",
                    ["solution_outline_id", "created_at"], schema="plm")
    op.create_foreign_key(
        "fk_sol_outlines__approved_version", "sol_outlines", "sol_outline_versions",
        ["current_approved_version_ref", "solution_outline_id", "project_id"],
        ["solution_outline_version_id", "solution_outline_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.create_table(
        "sol_outline_sections",
        sa.Column("solution_outline_section_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_outline_version_id", ident, nullable=False),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("solution_outline_version_id", "ordinal",
                            name="uq_sol_outline_sections__version_ordinal"),
        sa.UniqueConstraint("solution_outline_version_id", "solution_section_id",
                            name="uq_sol_outline_sections__version_section"),
        sa.ForeignKeyConstraint(["solution_outline_version_id", "solution_outline_id", "project_id"],
                                ["plm.sol_outline_versions.solution_outline_version_id",
                                 "plm.sol_outline_versions.solution_outline_id",
                                 "plm.sol_outline_versions.project_id"],
                                name="fk_sol_outline_sections__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["solution_section_id", "solution_outline_id", "project_id"],
                                ["plm.sol_sections.solution_section_id",
                                 "plm.sol_sections.solution_outline_id", "plm.sol_sections.project_id"],
                                name="fk_sol_outline_sections__section", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_outline_sections__ordinal"),
        schema="plm",
    )
    op.create_table(
        "sol_outline_requirement_refs",
        sa.Column("solution_outline_requirement_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_outline_version_id", ident, nullable=False),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("solution_outline_version_id", "ordinal",
                            name="uq_sol_outline_requirements__version_ordinal"),
        sa.UniqueConstraint("solution_outline_version_id", "requirement_version_id",
                            name="uq_sol_outline_requirements__version_requirement"),
        sa.ForeignKeyConstraint(["solution_outline_version_id", "solution_outline_id", "project_id"],
                                ["plm.sol_outline_versions.solution_outline_version_id",
                                 "plm.sol_outline_versions.solution_outline_id",
                                 "plm.sol_outline_versions.project_id"],
                                name="fk_sol_outline_requirements__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["requirement_version_id", "requirement_id", "project_id"],
                                ["plm.req_requirement_versions.requirement_version_id",
                                 "plm.req_requirement_versions.requirement_id",
                                 "plm.req_requirement_versions.project_id"],
                                name="fk_sol_outline_requirements__requirement", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_outline_requirements__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_outline_requirements__target", "sol_outline_requirement_refs",
                    ["requirement_version_id", "solution_outline_version_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_outline_version_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_solution_outline_version_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SolutionOutlineVersion downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("SolutionOutlineVersion history prevents downgrade")
    op.drop_constraint("fk_sol_outlines__approved_version", "sol_outlines", type_="foreignkey", schema="plm")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.drop_constraint("uq_sol_sections__id_outline_project", "sol_sections", type_="unique", schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_outline_version_foundation()")
    op.execute("DROP FUNCTION plm.reject_solution_outline_version_truncate()")
