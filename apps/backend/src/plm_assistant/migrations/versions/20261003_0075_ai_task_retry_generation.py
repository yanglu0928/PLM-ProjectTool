"""Add immutable AI Task explicit-retry generation lineage.

Revision ID: 20261003_0075
Revises: 20261003_0074
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261003_0075"
down_revision = "20261003_0074"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_ai_task_retry_generation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    source_task plm.ai_tasks%ROWTYPE;
    fresh_task plm.ai_tasks%ROWTYPE;
    source_job plm.job_jobs%ROWTYPE;
    fresh_job plm.job_jobs%ROWTYPE;
    prior_generation plm.ai_task_retry_generations%ROWTYPE;
    source_snapshot plm.ai_egress_authorization_snapshots%ROWTYPE;
    fresh_snapshot plm.ai_egress_authorization_snapshots%ROWTYPE;
    retry_event plm.aud_events%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'AI Task retry generation history is immutable';
    END IF;

    SELECT * INTO source_task FROM plm.ai_tasks
     WHERE ai_task_id=NEW.source_ai_task_id FOR KEY SHARE;
    SELECT * INTO fresh_task FROM plm.ai_tasks
     WHERE ai_task_id=NEW.new_ai_task_id FOR KEY SHARE;
    SELECT * INTO source_job FROM plm.job_jobs
     WHERE job_id=NEW.source_job_id FOR KEY SHARE;
    SELECT * INTO fresh_job FROM plm.job_jobs
     WHERE job_id=NEW.new_job_id FOR KEY SHARE;
    IF source_task.ai_task_id IS NULL OR fresh_task.ai_task_id IS NULL
       OR source_job.job_id IS NULL OR fresh_job.job_id IS NULL THEN
        RAISE EXCEPTION 'AI Task retry generation source is missing';
    END IF;

    IF source_task.job_ref IS DISTINCT FROM source_job.job_id
       OR source_task.task_state IS DISTINCT FROM source_job.state
       OR source_task.task_state NOT IN ('FAILED','CANCELLED')
       OR source_task.suggestion_state<>'NONE'
       OR source_task.completed_at IS NULL
       OR (source_task.task_state='FAILED' AND source_task.retryable IS DISTINCT FROM TRUE)
       OR source_job.lock_version<>NEW.expected_source_version
       OR source_job.owner_module<>'ai' OR source_job.job_type<>'AI_TASK_EXECUTE'
       OR fresh_task.job_ref IS DISTINCT FROM fresh_job.job_id
       OR fresh_task.task_state<>'QUEUED' OR fresh_task.suggestion_state<>'NONE'
       OR fresh_task.current_invocation_ref IS NOT NULL
       OR fresh_task.error_code IS NOT NULL OR fresh_task.retryable IS NOT NULL
       OR fresh_task.started_at IS NOT NULL OR fresh_task.completed_at IS NOT NULL
       OR fresh_task.lock_version<>0
       OR fresh_job.owner_module<>'ai' OR fresh_job.job_type<>'AI_TASK_EXECUTE'
       OR fresh_job.state<>'PENDING' OR fresh_job.lock_version<>0
       OR fresh_job.attempt_count<>0 OR fresh_job.fencing_token<>0
       OR fresh_job.lease_expires_at IS NOT NULL OR fresh_job.completed_at IS NOT NULL
       OR fresh_job.cancel_requested_by IS NOT NULL
       OR fresh_job.cancel_reason IS NOT NULL OR fresh_job.cancel_requested_at IS NOT NULL
       OR fresh_job.actor_ref IS DISTINCT FROM NEW.requested_by
       OR fresh_task.requested_by IS DISTINCT FROM NEW.requested_by
       OR fresh_job.trace_id IS DISTINCT FROM fresh_task.trace_id::text
       OR fresh_job.payload_refs->>'ai_task_id' IS DISTINCT FROM fresh_task.ai_task_id::text
       OR fresh_task.requested_at<source_task.completed_at
       OR NEW.created_at<fresh_task.requested_at THEN
        RAISE EXCEPTION 'AI Task retry terminal or Job binding is invalid';
    END IF;

    IF ROW(fresh_task.scope,fresh_task.project_id,fresh_task.task_type,
           fresh_task.input_fingerprint,fresh_task.prompt_policy_ref,
           fresh_task.output_schema_ref,fresh_task.context_policy_ref,
           fresh_task.prompt_template_ref,fresh_task.prompt_version_no,
           fresh_task.prompt_policy_version,fresh_task.task_parameters,
           fresh_task.task_parameters_fingerprint,fresh_task.content_plan_ref)
       IS DISTINCT FROM
       ROW(source_task.scope,source_task.project_id,source_task.task_type,
           source_task.input_fingerprint,source_task.prompt_policy_ref,
           source_task.output_schema_ref,source_task.context_policy_ref,
           source_task.prompt_template_ref,source_task.prompt_version_no,
           source_task.prompt_policy_version,source_task.task_parameters,
           source_task.task_parameters_fingerprint,source_task.content_plan_ref)
       OR ROW(fresh_job.scope,fresh_job.project_id,fresh_job.max_attempts)
          IS DISTINCT FROM
          ROW(source_job.scope,source_job.project_id,source_job.max_attempts) THEN
        RAISE EXCEPTION 'AI Task retry immutable snapshot drifted';
    END IF;

    IF EXISTS (
        (SELECT ref_ordinal,scope,project_id,owner_module,object_type,object_id,version_id
           FROM plm.ai_task_input_refs WHERE ai_task_id=source_task.ai_task_id
         EXCEPT
         SELECT ref_ordinal,scope,project_id,owner_module,object_type,object_id,version_id
           FROM plm.ai_task_input_refs WHERE ai_task_id=fresh_task.ai_task_id)
        UNION ALL
        (SELECT ref_ordinal,scope,project_id,owner_module,object_type,object_id,version_id
           FROM plm.ai_task_input_refs WHERE ai_task_id=fresh_task.ai_task_id
         EXCEPT
         SELECT ref_ordinal,scope,project_id,owner_module,object_type,object_id,version_id
           FROM plm.ai_task_input_refs WHERE ai_task_id=source_task.ai_task_id)
    ) THEN
        RAISE EXCEPTION 'AI Task retry input snapshot drifted';
    END IF;

    SELECT * INTO source_snapshot FROM plm.ai_egress_authorization_snapshots
     WHERE ai_task_id=source_task.ai_task_id FOR KEY SHARE;
    SELECT * INTO fresh_snapshot FROM plm.ai_egress_authorization_snapshots
     WHERE ai_task_id=fresh_task.ai_task_id FOR KEY SHARE;
    IF source_snapshot.egress_authorization_snapshot_id IS NULL
       OR fresh_snapshot.egress_authorization_snapshot_id IS NULL
       OR ROW(fresh_snapshot.scope,fresh_snapshot.project_id,
              fresh_snapshot.authorization_ref,fresh_snapshot.purpose_ref,
              fresh_snapshot.ai_provider_id,fresh_snapshot.provider_config_version_id,
              fresh_snapshot.data_region,fresh_snapshot.allowed_data_categories,
              fresh_snapshot.authorization_fingerprint,fresh_snapshot.approved_by,
              fresh_snapshot.ai_model_id,fresh_snapshot.approved_role,
              fresh_snapshot.preview_payload_fingerprint,
              fresh_snapshot.source_refs_fingerprint,fresh_snapshot.content_plan_ref,
              fresh_snapshot.max_payload_bytes,fresh_snapshot.max_input_tokens,
              fresh_snapshot.max_retry_attempts,
              fresh_snapshot.authorization_state_at_capture,
              fresh_snapshot.approved_at,fresh_snapshot.valid_until)
          IS DISTINCT FROM
          ROW(source_snapshot.scope,source_snapshot.project_id,
              source_snapshot.authorization_ref,source_snapshot.purpose_ref,
              source_snapshot.ai_provider_id,source_snapshot.provider_config_version_id,
              source_snapshot.data_region,source_snapshot.allowed_data_categories,
              source_snapshot.authorization_fingerprint,source_snapshot.approved_by,
              source_snapshot.ai_model_id,source_snapshot.approved_role,
              source_snapshot.preview_payload_fingerprint,
              source_snapshot.source_refs_fingerprint,source_snapshot.content_plan_ref,
              source_snapshot.max_payload_bytes,source_snapshot.max_input_tokens,
              source_snapshot.max_retry_attempts,
              source_snapshot.authorization_state_at_capture,
              source_snapshot.approved_at,source_snapshot.valid_until)
       OR NEW.generation_no>fresh_snapshot.max_retry_attempts THEN
        RAISE EXCEPTION 'AI Task retry egress snapshot drifted or limit exceeded';
    END IF;

    SELECT * INTO prior_generation FROM plm.ai_task_retry_generations
     WHERE new_ai_task_id=source_task.ai_task_id FOR KEY SHARE;
    IF prior_generation.new_ai_task_id IS NULL THEN
        IF NEW.root_ai_task_id IS DISTINCT FROM source_task.ai_task_id
           OR NEW.generation_no<>1 THEN
            RAISE EXCEPTION 'AI Task retry root generation is invalid';
        END IF;
    ELSIF NEW.root_ai_task_id IS DISTINCT FROM prior_generation.root_ai_task_id
       OR NEW.generation_no<>prior_generation.generation_no+1 THEN
        RAISE EXCEPTION 'AI Task retry descendant generation is invalid';
    END IF;

    SELECT * INTO retry_event FROM plm.aud_events
     WHERE audit_event_id=NEW.retry_audit_event_id FOR KEY SHARE;
    IF retry_event.audit_event_id IS NULL
       OR retry_event.event_scope<>'PROJECT'
       OR retry_event.target_project_id IS DISTINCT FROM fresh_task.project_id
       OR retry_event.actor_type<>'USER'
       OR retry_event.actor_id IS DISTINCT FROM NEW.requested_by
       OR retry_event.original_actor_id IS NOT NULL
       OR retry_event.actor_hint_digest IS NOT NULL
       OR retry_event.trace_id IS DISTINCT FROM fresh_task.trace_id
       OR retry_event.action<>'AI_TASK_USER_RETRY_REQUESTED'
       OR retry_event.outcome<>'SUCCESS'
       OR retry_event.target_owner_module<>'ai'
       OR retry_event.target_object_type<>'AI-04'
       OR retry_event.target_object_id IS DISTINCT FROM fresh_task.ai_task_id
       OR retry_event.target_version_id IS DISTINCT FROM source_task.ai_task_id
       OR retry_event.reason_code<>'USER_RETRY'
       OR retry_event.before_state IS DISTINCT FROM source_task.task_state
       OR retry_event.after_state<>'QUEUED'
       OR retry_event.occurred_at<fresh_task.requested_at
       OR NEW.created_at<retry_event.occurred_at THEN
        RAISE EXCEPTION 'AI Task retry Audit proof is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_task_retry_generation_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_task_retry_generations
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_task_retry_generation();

CREATE FUNCTION plm.guard_ai_task_retry_generation_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'AI Task retry generation history cannot be truncated';
END; $$;

CREATE TRIGGER trg_ai_task_retry_generation_no_truncate
BEFORE TRUNCATE ON plm.ai_task_retry_generations
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_task_retry_generation_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_task_retry_generations",
        sa.Column("new_ai_task_id", ident, primary_key=True),
        sa.Column("source_ai_task_id", ident, nullable=False),
        sa.Column("root_ai_task_id", ident, nullable=False),
        sa.Column("source_job_id", ident, nullable=False),
        sa.Column("new_job_id", ident, nullable=False),
        sa.Column("requested_by", ident, nullable=False),
        sa.Column("retry_audit_event_id", ident, nullable=False),
        sa.Column("generation_no", sa.Integer(), nullable=False),
        sa.Column("expected_source_version", sa.BigInteger(), nullable=False),
        sa.Column("first_job_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["new_ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                                name="fk_ai_task_retries__new_task",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["source_ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                                name="fk_ai_task_retries__source_task",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["root_ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                                name="fk_ai_task_retries__root_task",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["source_job_id"], ["plm.job_jobs.job_id"],
                                name="fk_ai_task_retries__source_job",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["new_job_id"], ["plm.job_jobs.job_id"],
                                name="fk_ai_task_retries__new_job",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["requested_by"], ["plm.auth_users.user_id"],
                                name="fk_ai_task_retries__requester",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["retry_audit_event_id"],
                                ["plm.aud_events.audit_event_id"],
                                name="fk_ai_task_retries__audit",
                                ondelete="NO ACTION"),
        sa.UniqueConstraint("new_job_id", name="uq_ai_task_retries__new_job"),
        sa.UniqueConstraint("retry_audit_event_id", name="uq_ai_task_retries__audit"),
        sa.UniqueConstraint("root_ai_task_id", "generation_no",
                            name="uq_ai_task_retries__root_generation"),
        sa.CheckConstraint(
            "new_ai_task_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND source_ai_task_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND root_ai_task_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND source_job_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND new_job_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND requested_by<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND retry_audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND new_ai_task_id<>source_ai_task_id AND new_job_id<>source_job_id "
            "AND generation_no BETWEEN 1 AND 10 "
            "AND expected_source_version>=0 AND first_job_version=0 "
            "AND isfinite(created_at)",
            name="ck_ai_task_retries__shape",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_ai_task_retries__root_generation", "ai_task_retry_generations",
        ["root_ai_task_id", "generation_no", "created_at"], schema="plm",
    )
    op.create_index(
        "ix_ai_task_retries__source", "ai_task_retry_generations",
        ["source_ai_task_id", "created_at"], schema="plm",
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Task retry generation downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_task_retry_generations IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_task_retry_generations) THEN
                RAISE EXCEPTION 'AI Task retry generation history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_task_retry_generation_no_truncate "
               "ON plm.ai_task_retry_generations")
    op.execute("DROP TRIGGER trg_ai_task_retry_generation_guard "
               "ON plm.ai_task_retry_generations")
    op.execute("DROP FUNCTION plm.guard_ai_task_retry_generation_truncate()")
    op.execute("DROP FUNCTION plm.guard_ai_task_retry_generation()")
    op.drop_index("ix_ai_task_retries__source",
                  table_name="ai_task_retry_generations", schema="plm")
    op.drop_index("ix_ai_task_retries__root_generation",
                  table_name="ai_task_retry_generations", schema="plm")
    op.drop_table("ai_task_retry_generations", schema="plm")
