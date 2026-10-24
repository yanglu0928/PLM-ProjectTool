"""Add closed ReferenceSolution identity, versions, and fixed source refs.

Revision ID: 20261008_0139
Revises: 20261008_0138
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0139"
down_revision = "20261008_0138"
branch_labels = None
depends_on = None

_TABLES = ("sol_reference_solutions", "sol_reference_versions",
           "sol_reference_document_refs", "sol_reference_evidence_refs")
_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ReferenceSolution Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_solution_reference_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ReferenceSolution history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "sol_reference_solutions",
        sa.Column("reference_solution_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("eligibility_state", sa.Text(), nullable=False,
                  server_default=sa.text("'REFERENCE_ONLY'")),
        sa.Column("eligibility_reason", sa.Text()),
        sa.Column("current_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("reference_solution_id", "scope", name="uq_sol_references__id_scope"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_sol_references__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_references__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_sol_references__scope"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                           name="ck_sol_references__name"),
        sa.CheckConstraint("eligibility_state IN ('REFERENCE_ONLY','ELIGIBLE','RESTRICTED','REVOKED')",
                           name="ck_sol_references__eligibility"),
        sa.CheckConstraint("eligibility_reason IS NULL OR "
                           "(char_length(eligibility_reason) BETWEEN 1 AND 2000 AND "
                           "eligibility_reason=btrim(eligibility_reason))",
                           name="ck_sol_references__reason"),
        sa.CheckConstraint("lock_version>=0", name="ck_sol_references__lock"),
        schema="plm",
    )
    op.create_index("ix_sol_references__scope_project", "sol_reference_solutions",
                    ["scope", "project_id", "eligibility_state"], schema="plm")
    op.create_table(
        "sol_reference_versions",
        sa.Column("reference_version_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("applicability", postgresql.JSONB(), nullable=False),
        sa.Column("source_project_class", sa.Text(), nullable=False),
        sa.Column("deidentification_class", sa.Text(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_document_count", sa.Integer(), nullable=False),
        sa.Column("declared_evidence_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("reference_version_id", "reference_solution_id", "scope",
                            name="uq_sol_reference_versions__id_parent_scope"),
        sa.UniqueConstraint("reference_solution_id", "version_no", name="uq_sol_reference_versions__parent_no"),
        sa.ForeignKeyConstraint(["reference_solution_id", "scope"],
                                ["plm.sol_reference_solutions.reference_solution_id",
                                 "plm.sol_reference_solutions.scope"],
                                name="fk_sol_reference_versions__parent", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_sol_reference_versions__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_ref", "reference_solution_id", "scope"],
                                ["plm.sol_reference_versions.reference_version_id",
                                 "plm.sol_reference_versions.reference_solution_id",
                                 "plm.sol_reference_versions.scope"],
                                name="fk_sol_reference_versions__supersedes", ondelete="NO ACTION",
                                deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_sol_reference_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_sol_reference_versions__scope"),
        sa.CheckConstraint("version_no>0", name="ck_sol_reference_versions__number"),
        sa.CheckConstraint("version_state='DRAFT'", name="ck_sol_reference_versions__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32", name="ck_sol_reference_versions__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(applicability)='object'", name="ck_sol_reference_versions__applicability"),
        sa.CheckConstraint("char_length(source_project_class) BETWEEN 1 AND 128 AND "
                           "source_project_class=btrim(source_project_class)",
                           name="ck_sol_reference_versions__source_class"),
        sa.CheckConstraint("char_length(deidentification_class) BETWEEN 1 AND 128 AND "
                           "deidentification_class=btrim(deidentification_class)",
                           name="ck_sol_reference_versions__deidentification"),
        sa.CheckConstraint("declared_document_count BETWEEN 1 AND 100 AND "
                           "declared_evidence_count BETWEEN 0 AND 500",
                           name="ck_sol_reference_versions__counts"),
        sa.CheckConstraint("supersedes_version_ref IS NULL OR supersedes_version_ref<>reference_version_id",
                           name="ck_sol_reference_versions__supersedes_not_self"),
        schema="plm",
    )
    op.create_index("ix_sol_reference_versions__parent_created", "sol_reference_versions",
                    ["reference_solution_id", "created_at"], schema="plm")
    op.create_foreign_key(
        "fk_sol_references__current_version", "sol_reference_solutions", "sol_reference_versions",
        ["current_version_ref", "reference_solution_id", "scope"],
        ["reference_version_id", "reference_solution_id", "scope"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.create_table(
        "sol_reference_document_refs",
        sa.Column("reference_document_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("reference_version_id", ident, nullable=False),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("reference_version_id", "ordinal", name="uq_sol_reference_documents__version_ordinal"),
        sa.UniqueConstraint("reference_version_id", "document_version_id",
                            name="uq_sol_reference_documents__version_document"),
        sa.ForeignKeyConstraint(["reference_version_id", "reference_solution_id", "scope"],
                                ["plm.sol_reference_versions.reference_version_id",
                                 "plm.sol_reference_versions.reference_solution_id",
                                 "plm.sol_reference_versions.scope"],
                                name="fk_sol_reference_documents__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["document_version_id"],
                                ["plm.doc_document_versions.document_version_id"],
                                name="fk_sol_reference_documents__document", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_reference_documents__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_reference_documents__target", "sol_reference_document_refs",
                    ["document_version_id", "reference_version_id"], schema="plm")
    op.create_table(
        "sol_reference_evidence_refs",
        sa.Column("reference_evidence_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("reference_version_id", ident, nullable=False),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("reference_version_id", "ordinal", name="uq_sol_reference_evidence__version_ordinal"),
        sa.UniqueConstraint("reference_version_id", "evidence_id", name="uq_sol_reference_evidence__version_evidence"),
        sa.ForeignKeyConstraint(["reference_version_id", "reference_solution_id", "scope"],
                                ["plm.sol_reference_versions.reference_version_id",
                                 "plm.sol_reference_versions.reference_solution_id",
                                 "plm.sol_reference_versions.scope"],
                                name="fk_sol_reference_evidence__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                                name="fk_sol_reference_evidence__evidence", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_sol_reference_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_sol_reference_evidence__target", "sol_reference_evidence_refs",
                    ["evidence_id", "reference_version_id"], schema="plm")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_reference_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_solution_reference_truncate()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline ReferenceSolution downgrade is disabled")
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")).scalar_one():
            raise RuntimeError("ReferenceSolution history prevents downgrade")
    op.drop_constraint("fk_sol_references__current_version", "sol_reference_solutions",
                       type_="foreignkey", schema="plm")
    for table in reversed(_TABLES):
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__owner ON plm.{table}"))
        op.execute(sa.text(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}"))
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_reference_foundation()")
    op.execute("DROP FUNCTION plm.reject_solution_reference_truncate()")
