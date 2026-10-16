"""Add closed RequirementVersion primary and approved pointer ownership FK.

Revision ID: 20261007_0116
Revises: 20261007_0115
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261007_0116"
down_revision = "20261007_0115"
branch_labels = None
depends_on = None

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_requirement_version_primary()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementVersion Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_requirement_version_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RequirementVersion history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "req_requirement_versions",
        sa.Column("requirement_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("title", sa.Text()),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("domain_name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("risk", sa.Text(), nullable=False),
        sa.Column("requirement_classification", sa.Text(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_source_count", sa.Integer(), nullable=False),
        sa.Column("declared_acceptance_count", sa.Integer(), nullable=False),
        sa.Column("declared_capability_count", sa.Integer(), nullable=False),
        sa.Column("declared_assumption_count", sa.Integer(), nullable=False),
        sa.Column("declared_exclusion_count", sa.Integer(), nullable=False),
        sa.Column("declared_dependency_count", sa.Integer(), nullable=False),
        sa.Column("declared_ai_task_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("requirement_version_id", "requirement_id", "project_id",
                            name="uq_req_versions__id_requirement_project"),
        sa.UniqueConstraint("requirement_id", "version_no",
                            name="uq_req_versions__requirement_no"),
        sa.ForeignKeyConstraint(["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_versions__requirement", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["supersedes_version_ref", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_versions__supersedes", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_req_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"],
                                ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_req_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_req_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_req_versions__number"),
        sa.CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
                           name="ck_req_versions__state"),
        sa.CheckConstraint("title IS NULL OR (char_length(title) BETWEEN 1 AND 500 AND title=btrim(title))",
                           name="ck_req_versions__title"),
        sa.CheckConstraint("char_length(statement)>0 AND statement=btrim(statement)",
                           name="ck_req_versions__statement"),
        sa.CheckConstraint("char_length(rationale)>0 AND rationale=btrim(rationale)",
                           name="ck_req_versions__rationale"),
        sa.CheckConstraint("char_length(domain_name) BETWEEN 1 AND 255 AND domain_name=btrim(domain_name)",
                           name="ck_req_versions__domain"),
        sa.CheckConstraint("priority IN ('LOW','MEDIUM','HIGH','URGENT')",
                           name="ck_req_versions__priority"),
        sa.CheckConstraint("risk IN ('LOW','MEDIUM','HIGH','CRITICAL')",
                           name="ck_req_versions__risk"),
        sa.CheckConstraint("requirement_classification IN ('STANDARD_FUNCTION','NONSTANDARD_FUNCTION','DIFFERENCE','PENDING_CONFIRMATION')",
                           name="ck_req_versions__classification"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_req_versions__fingerprint"),
        sa.CheckConstraint("declared_source_count>0 AND declared_acceptance_count>=0 AND declared_capability_count>=0 AND declared_assumption_count>=0 AND declared_exclusion_count>=0 AND declared_dependency_count>=0 AND declared_ai_task_count>=0",
                           name="ck_req_versions__counts"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR (review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                           name="ck_req_versions__review_shape"),
        sa.CheckConstraint("supersedes_version_ref IS NULL OR supersedes_version_ref<>requirement_version_id",
                           name="ck_req_versions__supersedes_not_self"),
        schema="plm",
    )
    op.create_index("ix_req_versions__requirement_created", "req_requirement_versions",
                    ["requirement_id", "created_at"], schema="plm")
    op.create_index("uq_req_versions__requirement_in_review", "req_requirement_versions",
                    ["requirement_id"], unique=True,
                    postgresql_where=sa.text("version_state='IN_REVIEW'"), schema="plm")
    op.create_index("uq_req_versions__requirement_approved", "req_requirement_versions",
                    ["requirement_id"], unique=True,
                    postgresql_where=sa.text("version_state='APPROVED'"), schema="plm")
    op.create_foreign_key(
        "fk_req_requirements__approved_version", "req_requirements",
        "req_requirement_versions",
        ["current_approved_version_ref", "requirement_id", "project_id"],
        ["requirement_version_id", "requirement_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION")
    op.execute(_GUARDS)
    op.execute("CREATE TRIGGER trg_req_requirement_versions__owner BEFORE INSERT OR UPDATE OR DELETE ON plm.req_requirement_versions FOR EACH ROW EXECUTE FUNCTION plm.guard_requirement_version_primary()")
    op.execute("CREATE TRIGGER trg_req_requirement_versions__no_truncate BEFORE TRUNCATE ON plm.req_requirement_versions FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_requirement_version_truncate()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RequirementVersion downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.req_requirement_versions)"
    )).scalar_one():
        raise RuntimeError("RequirementVersion history prevents downgrade")
    op.drop_constraint("fk_req_requirements__approved_version", "req_requirements",
                       schema="plm", type_="foreignkey")
    op.execute("DROP TRIGGER trg_req_requirement_versions__owner ON plm.req_requirement_versions")
    op.execute("DROP TRIGGER trg_req_requirement_versions__no_truncate ON plm.req_requirement_versions")
    op.drop_table("req_requirement_versions", schema="plm")
    op.execute("DROP FUNCTION plm.guard_requirement_version_primary()")
    op.execute("DROP FUNCTION plm.reject_requirement_version_truncate()")
