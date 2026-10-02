"""AI-04 complete input ResourceVersionRef identity without inventing legacy values.

Revision ID: 20261002_0065
Revises: 20261002_0064
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0065"
down_revision = "20261002_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_task_input_refs",
        sa.Column("object_id", postgresql.UUID(as_uuid=True)),
        schema="plm",
    )
    op.create_check_constraint(
        "ck_ai_task_inputs__object_id",
        "ai_task_input_refs",
        "object_id IS NULL OR object_id <> '00000000-0000-0000-0000-000000000000'::uuid",
        schema="plm",
    )
    op.drop_index("ix_ai_task_inputs__version", table_name="ai_task_input_refs", schema="plm")
    op.create_index(
        "ix_ai_task_inputs__object_version", "ai_task_input_refs",
        ["owner_module", "object_type", "object_id", "version_id"], schema="plm",
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION plm.guard_ai_task_input_ref()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_scope text; parent_project uuid; parent_state text;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'AI Task input reference history is immutable';
            END IF;
            IF NEW.object_id IS NULL THEN
                RAISE EXCEPTION 'AI Task input ObjectId is required for new references';
            END IF;
            SELECT scope, project_id, task_state INTO parent_scope, parent_project, parent_state
            FROM plm.ai_tasks WHERE ai_task_id = NEW.ai_task_id FOR KEY SHARE;
            IF NOT FOUND OR NEW.scope IS DISTINCT FROM parent_scope
               OR NEW.project_id IS DISTINCT FROM parent_project OR parent_state <> 'QUEUED' THEN
                RAISE EXCEPTION 'AI Task input scope mismatch';
            END IF;
            RETURN NEW;
        END; $$;
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Task input identity downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_task_input_refs IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_task_input_refs WHERE object_id IS NOT NULL) THEN
                RAISE EXCEPTION 'complete AI Task input identity prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION plm.guard_ai_task_input_ref()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_scope text; parent_project uuid; parent_state text;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'AI Task input reference history is immutable';
            END IF;
            SELECT scope, project_id, task_state INTO parent_scope, parent_project, parent_state
            FROM plm.ai_tasks WHERE ai_task_id = NEW.ai_task_id FOR KEY SHARE;
            IF NOT FOUND OR NEW.scope IS DISTINCT FROM parent_scope
               OR NEW.project_id IS DISTINCT FROM parent_project OR parent_state <> 'QUEUED' THEN
                RAISE EXCEPTION 'AI Task input scope mismatch';
            END IF;
            RETURN NEW;
        END; $$;
    """)
    op.drop_index("ix_ai_task_inputs__object_version",
                  table_name="ai_task_input_refs", schema="plm")
    op.create_index("ix_ai_task_inputs__version", "ai_task_input_refs",
                    ["owner_module", "object_type", "version_id"], schema="plm")
    op.drop_constraint("ck_ai_task_inputs__object_id", "ai_task_input_refs",
                       schema="plm", type_="check")
    op.drop_column("ai_task_input_refs", "object_id", schema="plm")
