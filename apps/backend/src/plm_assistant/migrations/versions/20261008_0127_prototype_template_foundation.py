"""Add PRT-04 GLOBAL/PROJECT template and immutable version foundation.

Revision ID: 20261008_0127
Revises: 20261008_0126
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261008_0127"
down_revision = "20261008_0126"
branch_labels = None
depends_on = None


_TABLES = (
    "prt_templates",
    "prt_template_versions",
    "prt_template_artifact_refs",
    "prt_template_command_results",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_template_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PrototypeTemplate Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_template_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PrototypeTemplate history cannot be truncated';
END; $$;
"""


def _scope_check(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "(scope='GLOBAL' AND project_id IS NULL) OR "
        "(scope='PROJECT' AND project_id IS NOT NULL)",
        name=name,
    )


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "prt_templates",
        sa.Column("prototype_template_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("template_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("current_template_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_templates__project", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_templates__creator", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["plm.auth_users.user_id"],
            name="fk_prt_templates__updater", ondelete="NO ACTION",
        ),
        _scope_check("ck_prt_templates__scope"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_templates__name",
        ),
        sa.CheckConstraint(
            "template_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_prt_templates__state",
        ),
        sa.CheckConstraint("lock_version>=0", name="ck_prt_templates__lock"),
        schema="plm",
    )
    op.create_index(
        "ix_prt_templates__scope_project_state", "prt_templates",
        ["scope", "project_id", "template_state", "prototype_template_id"],
        schema="plm",
    )
    op.create_table(
        "prt_template_versions",
        sa.Column("prototype_template_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_template_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PUBLISHED'")),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("supersedes_version_id", ident),
        sa.Column("layout_contract", postgresql.JSONB(), nullable=False),
        sa.Column("component_contract", postgresql.JSONB(), nullable=False),
        sa.Column("applicable_terminals", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint(
            "prototype_template_id", "version_no",
            name="uq_prt_template_versions__template_no",
        ),
        sa.UniqueConstraint(
            "prototype_template_version_id", "prototype_template_id",
            name="uq_prt_template_versions__id_template",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_template_id"], ["plm.prt_templates.prototype_template_id"],
            name="fk_prt_template_versions__template", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id", "prototype_template_id"],
            ["plm.prt_template_versions.prototype_template_version_id",
             "plm.prt_template_versions.prototype_template_id"],
            name="fk_prt_template_versions__supersedes", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_template_versions__project", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_template_versions__creator", ondelete="NO ACTION",
        ),
        _scope_check("ck_prt_template_versions__scope"),
        sa.CheckConstraint("version_no>0", name="ck_prt_template_versions__number"),
        sa.CheckConstraint("version_state='PUBLISHED'",
                           name="ck_prt_template_versions__state"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_prt_template_versions__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(layout_contract)='object'",
                           name="ck_prt_template_versions__layout"),
        sa.CheckConstraint("jsonb_typeof(component_contract)='object'",
                           name="ck_prt_template_versions__components"),
        sa.CheckConstraint("cardinality(applicable_terminals) BETWEEN 1 AND 16",
                           name="ck_prt_template_versions__terminals"),
        schema="plm",
    )
    op.create_index(
        "ix_prt_template_versions__scope_project", "prt_template_versions",
        ["scope", "project_id", "prototype_template_id", "version_no"],
        schema="plm",
    )
    op.create_foreign_key(
        "fk_prt_templates__current_version", "prt_templates",
        "prt_template_versions",
        ["current_template_version_ref", "prototype_template_id"],
        ["prototype_template_version_id", "prototype_template_id"],
        source_schema="plm",
        referent_schema="plm", ondelete="NO ACTION", deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "prt_template_artifact_refs",
        sa.Column("prototype_template_artifact_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_template_version_id", ident, nullable=False),
        sa.Column("prototype_template_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("artifact_kind", sa.Text(), nullable=False),
        sa.Column("target_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "prototype_template_version_id", "ordinal",
            name="uq_prt_template_artifact_refs__version_ordinal",
        ),
        sa.UniqueConstraint(
            "prototype_template_version_id", "artifact_kind", "target_id",
            name="uq_prt_template_artifact_refs__version_target",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_template_version_id", "prototype_template_id"],
            ["plm.prt_template_versions.prototype_template_version_id",
             "plm.prt_template_versions.prototype_template_id"],
            name="fk_prt_template_artifact_refs__version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_template_artifact_refs__project", ondelete="NO ACTION",
        ),
        _scope_check("ck_prt_template_artifact_refs__scope"),
        sa.CheckConstraint(
            "artifact_kind IN ('DOCUMENT_VERSION','OUTPUT_ARTIFACT')",
            name="ck_prt_template_artifact_refs__kind",
        ),
        sa.CheckConstraint("ordinal>0", name="ck_prt_template_artifact_refs__ordinal"),
        schema="plm",
    )
    op.create_index(
        "ix_prt_template_artifact_refs__target", "prt_template_artifact_refs",
        ["artifact_kind", "target_id", "prototype_template_version_id"],
        schema="plm",
    )
    op.create_table(
        "prt_template_command_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("prototype_template_id", ident, nullable=False),
        sa.Column("prototype_template_version_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["prototype_template_id"], ["plm.prt_templates.prototype_template_id"],
            name="fk_prt_template_command_results__template", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["prototype_template_version_id", "prototype_template_id"],
            ["plm.prt_template_versions.prototype_template_version_id",
             "plm.prt_template_versions.prototype_template_id"],
            name="fk_prt_template_command_results__version", ondelete="NO ACTION",
        ),
        _scope_check("ck_prt_template_command_results__scope"),
        sa.CheckConstraint("operation IN ('CREATE','REVISE')",
                           name="ck_prt_template_command_results__operation"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_template_command_results__name",
        ),
        sa.CheckConstraint("version_no>0",
                           name="ck_prt_template_command_results__number"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_prt_template_command_results__fingerprint"),
        sa.CheckConstraint("lock_version>=0",
                           name="ck_prt_template_command_results__lock"),
        schema="plm",
    )
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_prototype_template_foundation()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_prototype_template_truncate()"
        )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PrototypeTemplate downgrade is disabled")
    bind = op.get_bind()
    if any(bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
    )).scalar_one() for table in _TABLES):
        raise RuntimeError("PrototypeTemplate history prevents downgrade")
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    op.drop_constraint(
        "fk_prt_templates__current_version", "prt_templates",
        schema="plm", type_="foreignkey",
    )
    op.drop_table("prt_template_command_results", schema="plm")
    op.drop_table("prt_template_artifact_refs", schema="plm")
    op.drop_table("prt_template_versions", schema="plm")
    op.drop_table("prt_templates", schema="plm")
    op.execute("DROP FUNCTION plm.guard_prototype_template_foundation()")
    op.execute("DROP FUNCTION plm.reject_prototype_template_truncate()")
