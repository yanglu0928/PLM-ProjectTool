"""Require a unique immutable execution Job for every new AI Task.

Revision ID: 20261002_0066
Revises: 20261002_0065
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op


revision = "20261002_0066"
down_revision = "20261002_0065"
branch_labels = None
depends_on = None


_IDENTITY_GUARD_0066 = r"""
    CREATE OR REPLACE FUNCTION plm.guard_ai_task_identity()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        bound_owner text; bound_type text; bound_scope text; bound_project uuid;
        bound_actor uuid; bound_trace text; bound_task text;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'AI Task history cannot be deleted';
        END IF;
        IF TG_OP = 'INSERT' THEN
            IF NEW.job_ref IS NULL THEN
                RAISE EXCEPTION 'AI Task execution Job is required';
            END IF;
            SELECT owner_module, job_type, scope, project_id, actor_ref, trace_id,
                   payload_refs->>'ai_task_id'
              INTO bound_owner, bound_type, bound_scope, bound_project, bound_actor,
                   bound_trace, bound_task
              FROM plm.job_jobs WHERE job_id=NEW.job_ref FOR KEY SHARE;
            IF NOT FOUND OR bound_owner<>'ai' OR bound_type<>'AI_TASK_EXECUTE'
               OR bound_scope IS DISTINCT FROM NEW.scope
               OR bound_project IS DISTINCT FROM NEW.project_id
               OR bound_actor IS DISTINCT FROM NEW.requested_by
               OR bound_trace IS DISTINCT FROM NEW.trace_id::text
               OR bound_task IS DISTINCT FROM NEW.ai_task_id::text THEN
                RAISE EXCEPTION 'AI Task execution Job binding mismatch';
            END IF;
            RETURN NEW;
        END IF;
        IF (NEW.ai_task_id, NEW.scope, NEW.project_id, NEW.task_type,
            NEW.requested_by, NEW.input_fingerprint, NEW.prompt_policy_ref,
            NEW.output_schema_ref, NEW.context_policy_ref, NEW.job_ref, NEW.trace_id,
            NEW.requested_at, NEW.created_at)
           IS DISTINCT FROM
           (OLD.ai_task_id, OLD.scope, OLD.project_id, OLD.task_type,
            OLD.requested_by, OLD.input_fingerprint, OLD.prompt_policy_ref,
            OLD.output_schema_ref, OLD.context_policy_ref, OLD.job_ref, OLD.trace_id,
            OLD.requested_at, OLD.created_at) THEN
            RAISE EXCEPTION 'AI Task identity, input snapshot, and Job binding are immutable';
        END IF;
        IF NEW.lock_version <> OLD.lock_version + 1 THEN
            RAISE EXCEPTION 'AI Task lock version must advance once';
        END IF;
        IF OLD.task_state IN ('SUCCEEDED','FAILED','CANCELLED')
           AND NEW.task_state IS DISTINCT FROM OLD.task_state THEN
            RAISE EXCEPTION 'AI Task terminal state cannot revive';
        END IF;
        RETURN NEW;
    END; $$;
"""


_IDENTITY_GUARD_0065 = r"""
    CREATE OR REPLACE FUNCTION plm.guard_ai_task_identity()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'AI Task history cannot be deleted';
        END IF;
        IF (NEW.ai_task_id, NEW.scope, NEW.project_id, NEW.task_type,
            NEW.requested_by, NEW.input_fingerprint, NEW.prompt_policy_ref,
            NEW.output_schema_ref, NEW.context_policy_ref, NEW.trace_id,
            NEW.requested_at, NEW.created_at)
           IS DISTINCT FROM
           (OLD.ai_task_id, OLD.scope, OLD.project_id, OLD.task_type,
            OLD.requested_by, OLD.input_fingerprint, OLD.prompt_policy_ref,
            OLD.output_schema_ref, OLD.context_policy_ref, OLD.trace_id,
            OLD.requested_at, OLD.created_at) THEN
            RAISE EXCEPTION 'AI Task identity and input snapshot are immutable';
        END IF;
        IF NEW.lock_version <> OLD.lock_version + 1 THEN
            RAISE EXCEPTION 'AI Task lock version must advance once';
        END IF;
        IF OLD.task_state IN ('SUCCEEDED','FAILED','CANCELLED')
           AND NEW.task_state IS DISTINCT FROM OLD.task_state THEN
            RAISE EXCEPTION 'AI Task terminal state cannot revive';
        END IF;
        RETURN NEW;
    END; $$;
"""


def upgrade() -> None:
    op.create_index(
        "uq_ai_tasks__job_ref", "ai_tasks", ["job_ref"], unique=True,
        schema="plm", postgresql_where=sa.text("job_ref IS NOT NULL"),
    )
    op.execute("DROP TRIGGER trg_ai_task_identity_guard ON plm.ai_tasks")
    op.execute(_IDENTITY_GUARD_0066)
    op.execute("""
        CREATE TRIGGER trg_ai_task_identity_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_tasks
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_task_identity()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Task Job binding downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_tasks IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_tasks WHERE job_ref IS NOT NULL) THEN
                RAISE EXCEPTION 'complete AI Task Job binding prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_task_identity_guard ON plm.ai_tasks")
    op.execute(_IDENTITY_GUARD_0065)
    op.execute("""
        CREATE TRIGGER trg_ai_task_identity_guard
        BEFORE UPDATE OR DELETE ON plm.ai_tasks
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_task_identity()
    """)
    op.drop_index("uq_ai_tasks__job_ref", table_name="ai_tasks", schema="plm")
