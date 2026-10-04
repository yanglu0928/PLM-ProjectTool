"""AI-04 AITask identity and immutable input version references.

Revision ID: 20261002_0063
Revises: 20261002_0062
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0063"
down_revision = "20261002_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_tasks",
        sa.Column("ai_task_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("requested_by", ident, nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("prompt_policy_ref", sa.Text(), nullable=False),
        sa.Column("output_schema_ref", sa.Text(), nullable=False),
        sa.Column("context_policy_ref", sa.Text(), nullable=False),
        sa.Column("task_state", sa.Text(), nullable=False, server_default=sa.text("'QUEUED'")),
        sa.Column("suggestion_state", sa.Text(), nullable=False, server_default=sa.text("'NONE'")),
        sa.Column("accepted_domain_module", sa.Text()),
        sa.Column("accepted_domain_version_id", ident),
        sa.Column("job_ref", ident),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("retryable", sa.Boolean()),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("requested_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("started_at", timestamp),
        sa.Column("completed_at", timestamp),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_tasks__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["requested_by"], ["plm.auth_users.user_id"],
                                name="fk_ai_tasks__requester", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["job_ref"], ["plm.job_jobs.job_id"],
                                name="fk_ai_tasks__job", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_task_id", "scope", "project_id",
                            name="uq_ai_tasks__identity_scope", postgresql_nulls_not_distinct=True),
        sa.CheckConstraint("ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND requested_by <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid",
                           name="ck_ai_tasks__ids"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_ai_tasks__scope"),
        sa.CheckConstraint("task_type IN ('DOCUMENT_PARSE','CAPABILITY_EXTRACT',"
                           "'GAP_ANALYSIS','SURVEY_GENERATE','SURVEY_ANALYZE',"
                           "'REQUIREMENT_NORMALIZE','REQUIREMENT_MATCH','SOLUTION_SUGGEST',"
                           "'PROTOTYPE_GENERATE','SOLUTION_GENERATE','PLAN_GENERATE',"
                           "'OUTPUT_SUMMARIZE')", name="ck_ai_tasks__task_type"),
        sa.CheckConstraint("octet_length(input_fingerprint)=32 AND "
                           "prompt_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
                           "output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
                           "context_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
                           name="ck_ai_tasks__policy"),
        sa.CheckConstraint("task_state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED',"
                           "'CANCEL_REQUESTED','CANCELLED') AND "
                           "suggestion_state IN ('NONE','AVAILABLE','ACCEPTED_TO_DRAFT',"
                           "'REJECTED','SUPERSEDED') AND "
                           "(suggestion_state='NONE' OR task_state='SUCCEEDED') AND lock_version>=0",
                           name="ck_ai_tasks__state"),
        sa.CheckConstraint("(suggestion_state='ACCEPTED_TO_DRAFT' AND "
                           "accepted_domain_module IN ('handover','survey','requirement',"
                           "'prototype','solution','plan') AND accepted_domain_version_id IS NOT NULL) OR "
                           "(suggestion_state<>'ACCEPTED_TO_DRAFT' AND "
                           "accepted_domain_module IS NULL AND accepted_domain_version_id IS NULL)",
                           name="ck_ai_tasks__accepted"),
        sa.CheckConstraint("(started_at IS NULL OR started_at>=requested_at) AND "
                           "(completed_at IS NULL OR (started_at IS NOT NULL AND completed_at>=started_at)) "
                           "AND isfinite(requested_at) AND isfinite(created_at) AND "
                           "(started_at IS NULL OR isfinite(started_at)) AND "
                           "(completed_at IS NULL OR isfinite(completed_at))",
                           name="ck_ai_tasks__time"),
        sa.CheckConstraint("error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                           name="ck_ai_tasks__error"),
        schema="plm",
    )
    op.create_index("ix_ai_tasks__project_state", "ai_tasks",
                    ["project_id", "task_state", sa.text("requested_at DESC"),
                     sa.text("ai_task_id DESC")], schema="plm")
    op.create_index("ix_ai_tasks__requester", "ai_tasks",
                    ["requested_by", sa.text("requested_at DESC")], schema="plm")
    op.create_table(
        "ai_task_input_refs",
        sa.Column("input_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("ai_task_id", ident, nullable=False),
        sa.Column("ref_ordinal", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("owner_module", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("version_id", ident, nullable=False),
        sa.Column("added_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                                name="fk_ai_task_inputs__task", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_task_inputs__project", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_task_id", "ref_ordinal", name="uq_ai_task_inputs__ordinal"),
        sa.CheckConstraint("input_ref_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
                           "AND ref_ordinal BETWEEN 1 AND 1000", name="ck_ai_task_inputs__ids"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_ai_task_inputs__scope"),
        sa.CheckConstraint("owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND "
                           "object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND isfinite(added_at)",
                           name="ck_ai_task_inputs__ref"),
        schema="plm",
    )
    op.create_index("ix_ai_task_inputs__version", "ai_task_input_refs",
                    ["owner_module", "object_type", "version_id"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_ai_task_identity()
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
        CREATE TRIGGER trg_ai_task_identity_guard
        BEFORE UPDATE OR DELETE ON plm.ai_tasks
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_task_identity();
        CREATE FUNCTION plm.guard_ai_task_input_ref()
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
        CREATE TRIGGER trg_ai_task_input_ref_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_task_input_refs
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_task_input_ref();
        CREATE FUNCTION plm.guard_ai_task_truncate()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AI Task history cannot be truncated';
        END; $$;
        CREATE TRIGGER trg_ai_task_truncate_guard BEFORE TRUNCATE ON plm.ai_tasks
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_task_truncate();
        CREATE TRIGGER trg_ai_task_input_truncate_guard BEFORE TRUNCATE ON plm.ai_task_input_refs
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_task_truncate();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Task downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_task_input_refs, plm.ai_tasks IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_task_input_refs)
               OR EXISTS (SELECT 1 FROM plm.ai_tasks) THEN
                RAISE EXCEPTION 'AI Task history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_task_input_truncate_guard ON plm.ai_task_input_refs")
    op.execute("DROP TRIGGER trg_ai_task_truncate_guard ON plm.ai_tasks")
    op.execute("DROP TRIGGER trg_ai_task_input_ref_guard ON plm.ai_task_input_refs")
    op.execute("DROP TRIGGER trg_ai_task_identity_guard ON plm.ai_tasks")
    op.execute("DROP FUNCTION plm.guard_ai_task_truncate()")
    op.execute("DROP FUNCTION plm.guard_ai_task_input_ref()")
    op.execute("DROP FUNCTION plm.guard_ai_task_identity()")
    op.drop_index("ix_ai_task_inputs__version", table_name="ai_task_input_refs", schema="plm")
    op.drop_table("ai_task_input_refs", schema="plm")
    op.drop_index("ix_ai_tasks__requester", table_name="ai_tasks", schema="plm")
    op.drop_index("ix_ai_tasks__project_state", table_name="ai_tasks", schema="plm")
    op.drop_table("ai_tasks", schema="plm")
