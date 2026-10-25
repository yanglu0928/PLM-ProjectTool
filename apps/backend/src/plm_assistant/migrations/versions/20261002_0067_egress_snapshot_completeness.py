"""Complete egress authorization evidence for every new snapshot.

Revision ID: 20261002_0067
Revises: 20261002_0066
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0067"
down_revision = "20261002_0066"
branch_labels = None
depends_on = None


_GUARD_0067 = r"""
    CREATE OR REPLACE FUNCTION plm.guard_ai_egress_snapshot()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent_scope text; parent_project uuid; parent_state text;
            config_region text; element jsonb; v_model_provider uuid; v_model_state text;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'AI egress authorization snapshot history is immutable';
        END IF;
        IF NEW.ai_model_id IS NULL OR NEW.approved_role IS NULL
           OR NEW.preview_payload_fingerprint IS NULL OR NEW.source_refs_fingerprint IS NULL
           OR NEW.max_payload_bytes IS NULL OR NEW.max_input_tokens IS NULL
           OR NEW.max_retry_attempts IS NULL OR NEW.authorization_state_at_capture IS NULL THEN
            RAISE EXCEPTION 'complete AI egress authorization evidence is required';
        END IF;
        SELECT scope, project_id, task_state
          INTO parent_scope, parent_project, parent_state
          FROM plm.ai_tasks WHERE ai_task_id=NEW.ai_task_id FOR KEY SHARE;
        IF NOT FOUND OR NEW.scope IS DISTINCT FROM parent_scope
           OR NEW.project_id IS DISTINCT FROM parent_project
           OR parent_state NOT IN ('QUEUED','RUNNING') THEN
            RAISE EXCEPTION 'AI egress authorization task scope mismatch';
        END IF;
        SELECT data_region INTO config_region
          FROM plm.ai_provider_config_versions
         WHERE provider_config_version_id=NEW.provider_config_version_id
           AND ai_provider_id=NEW.ai_provider_id;
        IF NOT FOUND OR NEW.data_region IS DISTINCT FROM config_region THEN
            RAISE EXCEPTION 'AI egress authorization provider region mismatch';
        END IF;
        SELECT m.ai_provider_id, m.model_state INTO v_model_provider, v_model_state
          FROM plm.ai_models AS m WHERE m.ai_model_id=NEW.ai_model_id FOR KEY SHARE;
        IF NOT FOUND OR v_model_provider IS DISTINCT FROM NEW.ai_provider_id
           OR v_model_state<>'AVAILABLE' THEN
            RAISE EXCEPTION 'AI egress authorization model mismatch';
        END IF;
        FOR element IN SELECT value FROM jsonb_array_elements(NEW.allowed_data_categories)
        LOOP
            IF jsonb_typeof(element)<>'string' OR length(btrim(element #>> '{}'))=0
               OR length(element #>> '{}')>64 THEN
                RAISE EXCEPTION 'AI egress authorization data category is invalid';
            END IF;
        END LOOP;
        IF (SELECT count(*) FROM jsonb_array_elements(NEW.allowed_data_categories)) <>
           (SELECT count(DISTINCT value) FROM jsonb_array_elements(NEW.allowed_data_categories)) THEN
            RAISE EXCEPTION 'AI egress authorization data categories must be unique';
        END IF;
        RETURN NEW;
    END; $$;
"""


_GUARD_0066 = r"""
    CREATE OR REPLACE FUNCTION plm.guard_ai_egress_snapshot()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent_scope text; parent_project uuid; parent_state text;
            config_region text; element jsonb;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'AI egress authorization snapshot history is immutable';
        END IF;
        SELECT scope, project_id, task_state
          INTO parent_scope, parent_project, parent_state
          FROM plm.ai_tasks WHERE ai_task_id=NEW.ai_task_id FOR KEY SHARE;
        IF NOT FOUND OR NEW.scope IS DISTINCT FROM parent_scope
           OR NEW.project_id IS DISTINCT FROM parent_project
           OR parent_state NOT IN ('QUEUED','RUNNING') THEN
            RAISE EXCEPTION 'AI egress authorization task scope mismatch';
        END IF;
        SELECT data_region INTO config_region
          FROM plm.ai_provider_config_versions
         WHERE provider_config_version_id=NEW.provider_config_version_id
           AND ai_provider_id=NEW.ai_provider_id;
        IF NOT FOUND OR NEW.data_region IS DISTINCT FROM config_region THEN
            RAISE EXCEPTION 'AI egress authorization provider region mismatch';
        END IF;
        FOR element IN SELECT value FROM jsonb_array_elements(NEW.allowed_data_categories)
        LOOP
            IF jsonb_typeof(element)<>'string' OR length(btrim(element #>> '{}'))=0
               OR length(element #>> '{}')>64 THEN
                RAISE EXCEPTION 'AI egress authorization data category is invalid';
            END IF;
        END LOOP;
        IF (SELECT count(*) FROM jsonb_array_elements(NEW.allowed_data_categories)) <>
           (SELECT count(DISTINCT value) FROM jsonb_array_elements(NEW.allowed_data_categories)) THEN
            RAISE EXCEPTION 'AI egress authorization data categories must be unique';
        END IF;
        RETURN NEW;
    END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    table = "ai_egress_authorization_snapshots"
    for column in (
        sa.Column("ai_model_id", ident),
        sa.Column("approved_role", sa.Text()),
        sa.Column("preview_payload_fingerprint", sa.LargeBinary()),
        sa.Column("source_refs_fingerprint", sa.LargeBinary()),
        sa.Column("max_payload_bytes", sa.BigInteger()),
        sa.Column("max_input_tokens", sa.Integer()),
        sa.Column("max_retry_attempts", sa.Integer()),
        sa.Column("authorization_state_at_capture", sa.Text()),
    ):
        op.add_column(table, column, schema="plm")
    op.create_foreign_key("fk_ai_egress_snapshots__model", table, "ai_models",
                          ["ai_model_id"], ["ai_model_id"], source_schema="plm",
                          referent_schema="plm", ondelete="NO ACTION")
    op.create_check_constraint(
        "ck_ai_egress_snapshots__complete_v2", table,
        "(ai_model_id IS NULL AND approved_role IS NULL "
        "AND preview_payload_fingerprint IS NULL AND source_refs_fingerprint IS NULL "
        "AND max_payload_bytes IS NULL AND max_input_tokens IS NULL "
        "AND max_retry_attempts IS NULL AND authorization_state_at_capture IS NULL) OR "
        "(ai_model_id IS NOT NULL AND approved_role IN "
        "('PROJECT_MANAGER','CUSTOMER_MANAGER','DEPLOYMENT_ADMIN') "
        "AND octet_length(preview_payload_fingerprint)=32 "
        "AND octet_length(source_refs_fingerprint)=32 "
        "AND max_payload_bytes BETWEEN 1 AND 1073741824 "
        "AND max_input_tokens BETWEEN 1 AND 1048576 "
        "AND max_retry_attempts BETWEEN 1 AND 10 "
        "AND authorization_state_at_capture='AUTHORIZED')",
        schema="plm",
    )
    op.create_index("ix_ai_egress_snapshots__model", table, ["ai_model_id"], schema="plm")
    op.execute(_GUARD_0067)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline complete egress snapshot downgrade is disabled")
    table = "ai_egress_authorization_snapshots"
    op.execute("LOCK TABLE plm.ai_egress_authorization_snapshots IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_egress_authorization_snapshots
                       WHERE ai_model_id IS NOT NULL) THEN
                RAISE EXCEPTION 'complete AI egress authorization snapshot prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute(_GUARD_0066)
    op.drop_index("ix_ai_egress_snapshots__model", table_name=table, schema="plm")
    op.drop_constraint("ck_ai_egress_snapshots__complete_v2", table,
                       schema="plm", type_="check")
    op.drop_constraint("fk_ai_egress_snapshots__model", table,
                       schema="plm", type_="foreignkey")
    for name in (
        "authorization_state_at_capture", "max_retry_attempts", "max_input_tokens",
        "max_payload_bytes", "source_refs_fingerprint", "preview_payload_fingerprint",
        "approved_role", "ai_model_id",
    ):
        op.drop_column(table, name, schema="plm")
