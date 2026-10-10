"""Add closed SOL-05 SectionVersion and fixed requirement/evidence references.

Revision ID: 20261008_0138
Revises: 20261008_0137
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0138"
down_revision = "20261008_0137"
branch_labels = None
depends_on = None

_TABLES = ("sol_section_versions", "sol_section_requirement_refs", "sol_section_evidence_refs")
_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_section_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SolutionSectionVersion Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_solution_section_version_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'SolutionSectionVersion history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "sol_section_versions",
        sa.Column("solution_section_version_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_document_version_ref", ident),
        sa.Column("content_artifact_ref", ident),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(), nullable=False),
        sa.Column("exclusions", postgresql.JSONB(), nullable=False),
        sa.Column("declared_requirement_count", sa.Integer(), nullable=False),
        sa.Column("declared_evidence_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("solution_section_version_id", "solution_section_id", "project_id",
                            name="uq_sol_section_versions__id_section_project"),
        sa.UniqueConstraint("solution_section_id", "version_no", name="uq_sol_section_versions__section_no"),
        sa.ForeignKeyConstraint(["solution_section_id", "project_id"],
                                ["plm.sol_sections.solution_section_id", "plm.sol_sections.project_id"],
                                name="fk_sol_section_versions__section", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["content_document_version_ref"],
                                ["plm.doc_document_versions.document_version_id"],
                                name="fk_sol_section_versions__document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_ref", "solution_section_id", "project_id"],
                                ["plm.sol_section_versions.solution_section_version_id",
                                 "plm.sol_section_versions.solution_section_id", "plm.sol_section_versions.project_id"],
                                name="fk_sol_section_versions__supersedes", ondelete="NO ACTION",
                                deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_sol_section_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_sol_section_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_section_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_sol_section_versions__number"),
        sa.CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
                           name="ck_sol_section_versions__state"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 500 AND title=btrim(title)",
                           name="ck_sol_section_versions__title"),
        sa.CheckConstraint("(content_document_version_ref IS NULL) <> (content_artifact_ref IS NULL)",
                           name="ck_sol_section_versions__content_xor"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32", name="ck_sol_section_versions__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(assumptions)='array' AND jsonb_typeof(exclusions)='array'",
                           name="ck_sol_section_versions__declarations"),
        sa.CheckConstraint("declared_requirement_count BETWEEN 0 AND 500 AND declared_evidence_count BETWEEN 0 AND 500",
                           name="ck_sol_section_versions__counts"),
        sa.CheckConstraint("supersedes_version_ref IS NULL OR supersedes_version_ref<>solution_section_version_id",
                           name="ck_sol_section_versions__supersedes_not_self"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                           "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                           name="ck_sol_section_versions__review_pair"),
        schema="plm",
    )
    op.create_index("ix_sol_section_versions__section_created", "sol_section_versions",
                    ["solution_section_id", "created_at"], schema="plm")
    op.create_foreign_key(
        "fk_sol_sections__approved_version", "sol_sections", "sol_section_versions",
        ["current_approved_version_ref", "solution_section_id", "project_id"],
        ["solution_section_version_id", "solution_section_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.create_table(
        "sol_section_requirement_refs",
        sa.Column("solution_section_requirement_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("solution_section_version_id", ident, nullable=False),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("solution_section_version_id", "ordinal", name="uq_sol_section_requirements__version_ordinal"),
        sa.UniqueConstraint("solution_section_version_id", "requirement_version_id",
                            name="uq_sol_section_requirements__version_requirement"),
        sa.ForeignKeyConstraint(["solution_section_version_id", "solution_section_id", "project_id"],
                                ["plm.sol_section_versions.solution_section_version_id",
                                 "plm.sol_section_versions.solution_section_id", "plm.sol_section_versions.project_id"],
                                name="fk_sol_section_requirements__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["requirement_version_id", "requirement_id", "project_id"],
                                ["plm.req_requirement_versions.requirement_version_id",
                                 "plm.req_requirement_versions.requirement_id", "plm.req_requirement_versions.project_id"],
                                name="fk_sol_section_requirements__requirement", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_section_requirements__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_section_requirements__target", "sol_section_requirement_refs",
                    ["requirement_version_id", "solution_section_version_id"], schema="plm")
    op.create_table(
        "sol_section_evidence_refs",
        sa.Column("solution_section_evidence_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("solution_section_version_id", ident, nullable=False),
        sa.Column("solution_section_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("solution_section_version_id", "ordinal", name="uq_sol_section_evidence__version_ordinal"),
        sa.UniqueConstraint("solution_section_version_id", "evidence_id", name="uq_sol_section_evidence__version_evidence"),
        sa.ForeignKeyConstraint(["solution_section_version_id", "solution_section_id", "project_id"],
                                ["plm.sol_section_versions.solution_section_version_id",
                                 "plm.sol_section_versions.solution_section_id", "plm.sol_section_versions.project_id"],
                                name="fk_sol_section_evidence__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_sol_section_evidence__evidence", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_section_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_section_evidence__target", "sol_section_evidence_refs",
                    ["evidence_id", "solution_section_version_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_section_version_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_solution_section_version_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline SolutionSectionVersion downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("SolutionSectionVersion history prevents downgrade")
    op.drop_constraint("fk_sol_sections__approved_version", "sol_sections", type_="foreignkey", schema="plm")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_section_version_foundation()")
    op.execute("DROP FUNCTION plm.reject_solution_section_version_truncate()")
