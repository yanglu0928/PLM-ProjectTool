"""Add closed PRT-03 PrototypeVersion foundation.

Revision ID: 20261008_0130
Revises: 20261008_0129
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0130"
down_revision = "20261008_0129"
branch_labels = None
depends_on = None

_TABLES = (
    "prt_prototype_versions", "prt_version_artifact_refs",
    "prt_version_requirement_refs", "prt_interaction_specs",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PrototypeVersion Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_version_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PrototypeVersion history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "prt_prototype_versions",
        sa.Column("prototype_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("template_ref", ident, nullable=False),
        sa.Column("template_version_ref", ident, nullable=False),
        sa.Column("coverage_summary", postgresql.JSONB(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_artifact_count", sa.Integer(), nullable=False),
        sa.Column("declared_requirement_count", sa.Integer(), nullable=False),
        sa.Column("declared_interaction_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint(
            "prototype_version_id", "prototype_id", "project_id",
            name="uq_prt_versions__id_prototype_project",
        ),
        sa.UniqueConstraint(
            "prototype_id", "version_no", name="uq_prt_versions__prototype_no",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_versions__prototype", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_ref", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_versions__supersedes", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["template_version_ref", "template_ref"],
            ["plm.prt_template_versions.prototype_template_version_id",
             "plm.prt_template_versions.prototype_template_id"],
            name="fk_prt_versions__template_version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                                name="fk_prt_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_prt_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_prt_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_prt_versions__number"),
        sa.CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_prt_versions__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_prt_versions__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(coverage_summary)='object'",
                           name="ck_prt_versions__coverage"),
        sa.CheckConstraint(
            "declared_artifact_count BETWEEN 1 AND 100 AND "
            "declared_requirement_count BETWEEN 1 AND 200 AND "
            "declared_interaction_count=1", name="ck_prt_versions__counts"),
        sa.CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_prt_versions__review_shape"),
        sa.CheckConstraint(
            "supersedes_version_ref IS NULL OR supersedes_version_ref<>prototype_version_id",
            name="ck_prt_versions__supersedes_not_self"),
        schema="plm",
    )
    op.create_index("ix_prt_versions__prototype_created", "prt_prototype_versions",
                    ["prototype_id", "created_at"], schema="plm")
    op.create_index("uq_prt_versions__prototype_in_review", "prt_prototype_versions",
                    ["prototype_id"], unique=True, schema="plm",
                    postgresql_where=sa.text("version_state='IN_REVIEW'"))
    op.create_index("uq_prt_versions__prototype_approved", "prt_prototype_versions",
                    ["prototype_id"], unique=True, schema="plm",
                    postgresql_where=sa.text("version_state='APPROVED'"))
    op.create_foreign_key(
        "fk_prt_prototypes__approved_version", "prt_prototypes",
        "prt_prototype_versions",
        ["current_approved_version_ref", "prototype_id", "project_id"],
        ["prototype_version_id", "prototype_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.create_table(
        "prt_version_artifact_refs",
        sa.Column("prototype_version_artifact_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("artifact_kind", sa.Text(), nullable=False),
        sa.Column("target_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("prototype_version_id", "ordinal",
                            name="uq_prt_version_artifacts__version_ordinal"),
        sa.UniqueConstraint("prototype_version_id", "artifact_kind", "target_id",
                            name="uq_prt_version_artifacts__version_target"),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_version_artifacts__version", ondelete="NO ACTION"),
        sa.CheckConstraint("artifact_kind IN ('DOCUMENT_VERSION','OUTPUT_ARTIFACT')",
                           name="ck_prt_version_artifacts__kind"),
        sa.CheckConstraint("ordinal>0", name="ck_prt_version_artifacts__ordinal"),
        schema="plm",
    )
    op.create_index("ix_prt_version_artifacts__target", "prt_version_artifact_refs",
                    ["artifact_kind", "target_id", "prototype_version_id"], schema="plm")
    op.create_table(
        "prt_version_requirement_refs",
        sa.Column("prototype_version_requirement_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("requirement_id", ident, nullable=False),
        sa.Column("requirement_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("prototype_version_id", "ordinal",
                            name="uq_prt_version_requirements__version_ordinal"),
        sa.UniqueConstraint("prototype_version_id", "requirement_version_id",
                            name="uq_prt_version_requirements__version_target"),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_version_requirements__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_prt_version_requirements__requirement", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_prt_version_requirements__ordinal"),
        schema="plm",
    )
    op.create_index("ix_prt_version_requirements__target", "prt_version_requirement_refs",
                    ["requirement_version_id", "prototype_version_id"], schema="plm")
    op.create_table(
        "prt_interaction_specs",
        sa.Column("prototype_interaction_spec_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("prototype_version_id", name="uq_prt_interactions__version"),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_interactions__version", ondelete="NO ACTION"),
        sa.CheckConstraint("schema_version=1", name="ck_prt_interactions__schema"),
        sa.CheckConstraint("jsonb_typeof(specification)='object'",
                           name="ck_prt_interactions__specification"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_prt_interactions__fingerprint"),
        schema="plm",
    )
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_version_foundation()")
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_prototype_version_truncate()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PrototypeVersion downgrade is disabled")
    bind = op.get_bind()
    if any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _TABLES):
        raise RuntimeError("PrototypeVersion history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    op.drop_constraint("fk_prt_prototypes__approved_version", "prt_prototypes",
                       schema="plm", type_="foreignkey")
    op.drop_table("prt_interaction_specs", schema="plm")
    op.drop_table("prt_version_requirement_refs", schema="plm")
    op.drop_table("prt_version_artifact_refs", schema="plm")
    op.drop_table("prt_prototype_versions", schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_version_foundation()")
    op.execute("DROP FUNCTION plm.reject_prototype_version_truncate()")
