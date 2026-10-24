"""Require every new AI Invocation to bind the Task's exact Content Plan.

Revision ID: 20261003_0073
Revises: 20261003_0072
"""

from __future__ import annotations

from alembic import context, op


revision = "20261003_0073"
down_revision = "20261003_0072"
branch_labels = None
depends_on = None


_GUARD = r"""
CREATE FUNCTION plm.guard_ai_invocation_content_plan_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    task_row plm.ai_tasks%ROWTYPE;
    snapshot_row plm.ai_egress_authorization_snapshots%ROWTYPE;
    plan_row plm.ai_execution_content_plans%ROWTYPE;
BEGIN
    IF NEW.content_plan_ref IS NULL
       OR NEW.egress_authorization_mode<>'AUTHORIZED'
       OR NEW.egress_authorization_snapshot_id IS NULL THEN
        RAISE EXCEPTION 'new AI Invocation requires an authorized Content Plan';
    END IF;

    SELECT * INTO task_row FROM plm.ai_tasks
     WHERE ai_task_id=NEW.ai_task_id FOR KEY SHARE;
    IF NOT FOUND
       OR ROW(NEW.scope,NEW.project_id,NEW.input_fingerprint,
              NEW.prompt_template_id,NEW.prompt_version_no,
              NEW.output_schema_ref,NEW.content_plan_ref)
          IS DISTINCT FROM
          ROW(task_row.scope,task_row.project_id,task_row.input_fingerprint,
              task_row.prompt_template_ref,task_row.prompt_version_no,
              task_row.output_schema_ref,task_row.content_plan_ref) THEN
        RAISE EXCEPTION 'AI Invocation does not match Task Content Plan identity';
    END IF;

    SELECT * INTO snapshot_row FROM plm.ai_egress_authorization_snapshots
     WHERE egress_authorization_snapshot_id=NEW.egress_authorization_snapshot_id
       AND ai_task_id=NEW.ai_task_id FOR KEY SHARE;
    IF NOT FOUND
       OR ROW(snapshot_row.scope,snapshot_row.project_id,
              snapshot_row.ai_provider_id,snapshot_row.provider_config_version_id,
              snapshot_row.ai_model_id,snapshot_row.source_refs_fingerprint,
              snapshot_row.preview_payload_fingerprint,
              snapshot_row.content_plan_ref,snapshot_row.authorization_state_at_capture)
          IS DISTINCT FROM
          ROW(NEW.scope,NEW.project_id,NEW.ai_provider_id,
              NEW.provider_config_version_id,NEW.ai_model_id,
              NEW.input_fingerprint,NEW.request_payload_fingerprint,
              NEW.content_plan_ref,'AUTHORIZED') THEN
        RAISE EXCEPTION 'AI Invocation does not match authorization snapshot Content Plan';
    END IF;

    SELECT * INTO plan_row FROM plm.ai_execution_content_plans
     WHERE content_plan_id=NEW.content_plan_ref FOR KEY SHARE;
    IF NOT FOUND
       OR ROW(plan_row.project_id,plan_row.task_type,
              plan_row.source_refs_fingerprint,plan_row.prompt_policy_ref,
              plan_row.prompt_policy_version,plan_row.prompt_template_id,
              plan_row.prompt_version_no,plan_row.output_schema_ref,
              plan_row.schema_version,plan_row.task_parameters_fingerprint,
              plan_row.context_policy_ref,plan_row.retrieval_run_id,
              plan_row.context_bundle_fingerprint,plan_row.ai_provider_id,
              plan_row.provider_config_version_id,plan_row.ai_model_id,
              plan_row.model_revision,plan_row.payload_fingerprint)
          IS DISTINCT FROM
          ROW(NEW.project_id,task_row.task_type,NEW.input_fingerprint,
              task_row.prompt_policy_ref,task_row.prompt_policy_version,
              NEW.prompt_template_id,NEW.prompt_version_no,
              NEW.output_schema_ref,NEW.schema_version,
              task_row.task_parameters_fingerprint,task_row.context_policy_ref,
              NEW.retrieval_run_ref,NEW.context_bundle_fingerprint,
              NEW.ai_provider_id,NEW.provider_config_version_id,
              NEW.ai_model_id,NEW.model_revision_observed,
              NEW.request_payload_fingerprint) THEN
        RAISE EXCEPTION 'AI Invocation request snapshot does not match Content Plan';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_invocations__content_plan_insert
BEFORE INSERT ON plm.ai_invocations
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_invocation_content_plan_insert();
"""


def upgrade() -> None:
    op.execute(_GUARD)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Invocation Content Plan guard downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_invocations IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_invocations
                       WHERE content_plan_ref IS NOT NULL) THEN
                RAISE EXCEPTION 'AI Invocation Content Plan history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute(
        "DROP TRIGGER trg_ai_invocations__content_plan_insert "
        "ON plm.ai_invocations"
    )
    op.execute("DROP FUNCTION plm.guard_ai_invocation_content_plan_insert()")
