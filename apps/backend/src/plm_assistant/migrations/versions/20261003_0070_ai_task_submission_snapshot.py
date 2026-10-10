"""AI Task Prompt version and minimal parameter submission snapshot.

Revision ID: 20261003_0070
Revises: 20261003_0069
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261003_0070"
down_revision = "20261003_0069"
branch_labels = None
depends_on = None


_GUARD = r"""
    CREATE OR REPLACE FUNCTION plm.guard_ai_task_submission_snapshot()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_template_task_type text; v_template_state text; v_active_version bigint;
            v_version_output text; v_version_rag text; v_parameter_count bigint;
    BEGIN
        IF TG_OP='UPDATE' AND (
            NEW.prompt_template_ref IS DISTINCT FROM OLD.prompt_template_ref OR
            NEW.prompt_version_no IS DISTINCT FROM OLD.prompt_version_no OR
            NEW.task_parameters IS DISTINCT FROM OLD.task_parameters OR
            NEW.task_parameters_fingerprint IS DISTINCT FROM OLD.task_parameters_fingerprint
        ) THEN
            RAISE EXCEPTION 'AI Task submission snapshot is immutable';
        END IF;
        IF NEW.prompt_template_ref IS NULL THEN
            RETURN NEW;
        END IF;
        SELECT task_type, template_state, active_version_no
          INTO v_template_task_type, v_template_state, v_active_version
          FROM plm.ai_prompt_templates
         WHERE prompt_template_id=NEW.prompt_template_ref FOR KEY SHARE;
        IF NOT FOUND OR v_template_task_type IS DISTINCT FROM NEW.task_type
           OR v_template_state<>'ACTIVE'
           OR v_active_version IS DISTINCT FROM NEW.prompt_version_no THEN
            RAISE EXCEPTION 'AI Task Prompt snapshot is not current and compatible';
        END IF;
        SELECT output_schema_ref, rag_policy_ref
          INTO v_version_output, v_version_rag
          FROM plm.ai_prompt_versions
         WHERE prompt_template_id=NEW.prompt_template_ref
           AND version_no=NEW.prompt_version_no FOR KEY SHARE;
        IF NOT FOUND OR v_version_output IS DISTINCT FROM NEW.output_schema_ref
           OR v_version_rag IS DISTINCT FROM NEW.context_policy_ref THEN
            RAISE EXCEPTION 'AI Task Prompt policy snapshot mismatch';
        END IF;
        IF jsonb_typeof(NEW.task_parameters) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'AI Task minimal parameters must be a JSON object';
        END IF;
        SELECT count(*) INTO v_parameter_count
          FROM jsonb_object_keys(NEW.task_parameters);
        IF v_parameter_count>16 OR octet_length(convert_to(NEW.task_parameters::text,'UTF8'))>16384
           OR sha256(convert_to(NEW.task_parameters::text,'UTF8'))
              IS DISTINCT FROM NEW.task_parameters_fingerprint THEN
            RAISE EXCEPTION 'AI Task minimal parameters are invalid';
        END IF;
        RETURN NEW;
    END; $$;
"""


def upgrade() -> None:
    table = "ai_tasks"
    op.add_column(table, sa.Column("prompt_template_ref", postgresql.UUID(as_uuid=True)),
                  schema="plm")
    op.add_column(table, sa.Column("prompt_version_no", sa.BigInteger()), schema="plm")
    op.add_column(table, sa.Column("task_parameters", postgresql.JSONB()), schema="plm")
    op.add_column(table, sa.Column("task_parameters_fingerprint", sa.LargeBinary()),
                  schema="plm")
    op.create_foreign_key(
        "fk_ai_tasks__prompt_version", table, "ai_prompt_versions",
        ["prompt_template_ref", "prompt_version_no"],
        ["prompt_template_id", "version_no"], source_schema="plm",
        referent_schema="plm", ondelete="NO ACTION",
    )
    op.create_check_constraint(
        "ck_ai_tasks__submission_snapshot", table,
        "(prompt_template_ref IS NULL AND prompt_version_no IS NULL "
        "AND task_parameters IS NULL AND task_parameters_fingerprint IS NULL) OR "
        "(prompt_template_ref IS NOT NULL "
        "AND prompt_template_ref<>'00000000-0000-0000-0000-000000000000'::uuid "
        "AND prompt_version_no BETWEEN 1 AND 9223372036854775807 "
        "AND jsonb_typeof(task_parameters)='object' "
        "AND octet_length(task_parameters_fingerprint)=32)",
        schema="plm",
    )
    op.create_index(
        "ix_ai_tasks__prompt_version", table,
        ["prompt_template_ref", "prompt_version_no"], schema="plm",
    )
    op.execute(_GUARD)
    op.execute("""
        CREATE TRIGGER trg_ai_tasks__submission_snapshot
        BEFORE INSERT OR UPDATE ON plm.ai_tasks
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_task_submission_snapshot()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Task submission snapshot downgrade is disabled")
    table = "ai_tasks"
    op.execute("LOCK TABLE plm.ai_tasks IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_tasks WHERE prompt_template_ref IS NOT NULL) THEN
                RAISE EXCEPTION 'AI Task submission history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_tasks__submission_snapshot ON plm.ai_tasks")
    op.execute("DROP FUNCTION plm.guard_ai_task_submission_snapshot()")
    op.drop_index("ix_ai_tasks__prompt_version", table_name=table, schema="plm")
    op.drop_constraint("ck_ai_tasks__submission_snapshot", table,
                       schema="plm", type_="check")
    op.drop_constraint("fk_ai_tasks__prompt_version", table,
                       schema="plm", type_="foreignkey")
    for name in (
        "task_parameters_fingerprint", "task_parameters",
        "prompt_version_no", "prompt_template_ref",
    ):
        op.drop_column(table, name, schema="plm")
