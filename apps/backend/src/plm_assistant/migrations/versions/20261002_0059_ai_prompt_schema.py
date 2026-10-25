"""AI-03 deployment prompt identities and immutable versions.

Revision ID: 20261002_0059
Revises: 20261002_0058
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0059"
down_revision = "20261002_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_prompt_templates",
        sa.Column("prompt_template_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False, server_default=sa.text("'DEPLOYMENT'")),
        sa.Column("template_state", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("active_version_no", sa.BigInteger()),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_ai_prompt_templates__created_by__auth_users", ondelete="NO ACTION"),
        sa.CheckConstraint("prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid",
                           name="ck_ai_prompt_templates__ids"),
        sa.CheckConstraint("task_type IN ('DOCUMENT_PARSE','CAPABILITY_EXTRACT','GAP_ANALYSIS',"
                           "'SURVEY_GENERATE','SURVEY_ANALYZE','REQUIREMENT_NORMALIZE',"
                           "'REQUIREMENT_MATCH','SOLUTION_SUGGEST','PROTOTYPE_GENERATE',"
                           "'SOLUTION_GENERATE','PLAN_GENERATE','OUTPUT_SUMMARIZE')",
                           name="ck_ai_prompt_templates__task_type"),
        sa.CheckConstraint("scope = 'DEPLOYMENT' AND template_state IN ('DRAFT','ACTIVE','RETIRED') "
                           "AND (template_state <> 'DRAFT' OR active_version_no IS NULL) "
                           "AND (template_state <> 'ACTIVE' OR active_version_no IS NOT NULL) "
                           "AND lock_version >= 0 AND isfinite(created_at)",
                           name="ck_ai_prompt_templates__state"),
        schema="plm",
    )
    op.create_table(
        "ai_prompt_versions",
        sa.Column("prompt_template_id", ident, primary_key=True),
        sa.Column("version_no", sa.BigInteger(), primary_key=True),
        sa.Column("system_template", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("system_template_hash", sa.Text(), nullable=False),
        sa.Column("user_template_hash", sa.Text(), nullable=False),
        sa.Column("output_schema_ref", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.BigInteger(), nullable=False),
        sa.Column("rag_policy_ref", sa.Text(), nullable=False),
        sa.Column("provider_policy_ref", sa.Text(), nullable=False),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["prompt_template_id"], ["plm.ai_prompt_templates.prompt_template_id"],
                                name="fk_ai_prompt_versions__prompt_template_id__ai_prompt_templates",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_ai_prompt_versions__created_by__auth_users", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no > 0 AND version_no <= 9223372036854775807 "
                           "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND length(system_template) BETWEEN 1 AND 65536 "
                           "AND length(user_template) BETWEEN 1 AND 65536 "
                           "AND system_template_hash ~ '^[0-9a-f]{64}$' "
                           "AND user_template_hash ~ '^[0-9a-f]{64}$' "
                           "AND output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
                           "AND schema_version BETWEEN 1 AND 2147483647 "
                           "AND rag_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
                           "AND provider_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
                           "AND isfinite(created_at)", name="ck_ai_prompt_versions__shape"),
        schema="plm",
    )
    op.create_foreign_key(
        "fk_ai_prompt_templates__active_version", "ai_prompt_templates", "ai_prompt_versions",
        ["prompt_template_id", "active_version_no"], ["prompt_template_id", "version_no"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_ai_prompt_version()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'PromptVersion history is immutable';
        END; $$;
        CREATE TRIGGER trg_ai_prompt_version_guard
        BEFORE UPDATE OR DELETE ON plm.ai_prompt_versions
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_prompt_version();
        CREATE TRIGGER trg_ai_prompt_version_truncate_guard
        BEFORE TRUNCATE ON plm.ai_prompt_versions
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_prompt_version();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prompt downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_prompt_templates, plm.ai_prompt_versions IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_prompt_templates)
               OR EXISTS (SELECT 1 FROM plm.ai_prompt_versions) THEN
                RAISE EXCEPTION 'Prompt history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_prompt_version_truncate_guard ON plm.ai_prompt_versions")
    op.execute("DROP TRIGGER trg_ai_prompt_version_guard ON plm.ai_prompt_versions")
    op.execute("DROP FUNCTION plm.guard_ai_prompt_version()")
    op.drop_constraint("fk_ai_prompt_templates__active_version", "ai_prompt_templates", schema="plm")
    op.drop_table("ai_prompt_versions", schema="plm")
    op.drop_table("ai_prompt_templates", schema="plm")
