"""Persist the exact AI Task deployment policy version.

Revision ID: 20261003_0071
Revises: 20261003_0070
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op


revision = "20261003_0071"
down_revision = "20261003_0070"
branch_labels = None
depends_on = None


_GUARD_0071 = r"""
    CREATE OR REPLACE FUNCTION plm.guard_ai_task_submission_snapshot()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_template_task_type text; v_template_state text; v_active_version bigint;
            v_version_output text; v_version_rag text; v_parameter_count bigint;
    BEGIN
        IF TG_OP='UPDATE' AND (
            NEW.prompt_template_ref IS DISTINCT FROM OLD.prompt_template_ref OR
            NEW.prompt_version_no IS DISTINCT FROM OLD.prompt_version_no OR
            NEW.prompt_policy_version IS DISTINCT FROM OLD.prompt_policy_version OR
            NEW.task_parameters IS DISTINCT FROM OLD.task_parameters OR
            NEW.task_parameters_fingerprint IS DISTINCT FROM OLD.task_parameters_fingerprint
        ) THEN
            RAISE EXCEPTION 'AI Task submission snapshot is immutable';
        END IF;
        IF NEW.prompt_template_ref IS NULL THEN
            RETURN NEW;
        END IF;
        IF NEW.prompt_policy_version NOT BETWEEN 1 AND 2147483647 THEN
            RAISE EXCEPTION 'AI Task deployment policy version is invalid';
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


_GUARD_0070 = _GUARD_0071.replace(
    "            NEW.prompt_policy_version IS DISTINCT FROM OLD.prompt_policy_version OR\n",
    "",
).replace(
    "        IF NEW.prompt_policy_version NOT BETWEEN 1 AND 2147483647 THEN\n"
    "            RAISE EXCEPTION 'AI Task deployment policy version is invalid';\n"
    "        END IF;\n",
    "",
)


def upgrade() -> None:
    table = "ai_tasks"
    op.add_column(table, sa.Column("prompt_policy_version", sa.BigInteger()), schema="plm")
    op.drop_constraint("ck_ai_tasks__submission_snapshot", table,
                       schema="plm", type_="check")
    op.create_check_constraint(
        "ck_ai_tasks__submission_snapshot", table,
        "(prompt_template_ref IS NULL AND prompt_version_no IS NULL "
        "AND prompt_policy_version IS NULL "
        "AND task_parameters IS NULL AND task_parameters_fingerprint IS NULL) OR "
        "(prompt_template_ref IS NOT NULL "
        "AND prompt_template_ref<>'00000000-0000-0000-0000-000000000000'::uuid "
        "AND prompt_version_no BETWEEN 1 AND 9223372036854775807 "
        "AND prompt_policy_version BETWEEN 1 AND 2147483647 "
        "AND jsonb_typeof(task_parameters)='object' "
        "AND octet_length(task_parameters_fingerprint)=32)",
        schema="plm",
    )
    op.execute(_GUARD_0071)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Task policy version downgrade is disabled")
    table = "ai_tasks"
    op.execute("LOCK TABLE plm.ai_tasks IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_tasks WHERE prompt_policy_version IS NOT NULL) THEN
                RAISE EXCEPTION 'AI Task policy-version history prevents downgrade';
            END IF;
        END $$;
    """)
    op.drop_constraint("ck_ai_tasks__submission_snapshot", table,
                       schema="plm", type_="check")
    op.execute(_GUARD_0070)
    op.drop_column(table, "prompt_policy_version", schema="plm")
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
