"""AI-04 immutable Invocation attempts, context refs, and egress snapshots.

Revision ID: 20261002_0064
Revises: 20261002_0063
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0064"
down_revision = "20261002_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_egress_authorization_snapshots",
        sa.Column("egress_authorization_snapshot_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("ai_task_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("authorization_ref", ident, nullable=False),
        sa.Column("purpose_ref", sa.Text(), nullable=False),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_config_version_id", ident, nullable=False),
        sa.Column("data_region", sa.Text(), nullable=False),
        sa.Column("allowed_data_categories", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("approved_by", ident, nullable=False),
        sa.Column("approved_at", timestamp, nullable=False),
        sa.Column("valid_until", timestamp, nullable=False),
        sa.Column("captured_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                                name="fk_ai_egress_snapshots__task", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_egress_snapshots__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_egress_snapshots__provider_config", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["approved_by"], ["plm.auth_users.user_id"],
                                name="fk_ai_egress_snapshots__approver", ondelete="NO ACTION"),
        sa.UniqueConstraint("egress_authorization_snapshot_id", "ai_task_id",
                            name="uq_ai_egress_snapshots__identity_task"),
        sa.CheckConstraint(
            "egress_authorization_snapshot_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND authorization_ref <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND approved_by <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_egress_snapshots__ids"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_ai_egress_snapshots__scope"),
        sa.CheckConstraint(
            "purpose_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND data_region ~ '^[a-z][a-z0-9-]{0,63}$' "
            "AND jsonb_typeof(allowed_data_categories)='array' "
            "AND jsonb_array_length(allowed_data_categories) BETWEEN 1 AND 64 "
            "AND octet_length(authorization_fingerprint)=32",
            name="ck_ai_egress_snapshots__policy"),
        sa.CheckConstraint(
            "approved_at<=captured_at AND captured_at<valid_until "
            "AND isfinite(approved_at) AND isfinite(valid_until) AND isfinite(captured_at)",
            name="ck_ai_egress_snapshots__time"),
        schema="plm",
    )
    op.create_index("ix_ai_egress_snapshots__task_time", "ai_egress_authorization_snapshots",
                    ["ai_task_id", "captured_at"], schema="plm")

    op.create_table(
        "ai_invocations",
        sa.Column("ai_invocation_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("ai_task_id", ident, nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_config_version_id", ident, nullable=False),
        sa.Column("ai_model_id", ident, nullable=False),
        sa.Column("model_revision_observed", sa.Text(), nullable=False),
        sa.Column("prompt_template_id", ident, nullable=False),
        sa.Column("prompt_version_no", sa.BigInteger(), nullable=False),
        sa.Column("output_schema_ref", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.BigInteger(), nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("egress_authorization_mode", sa.Text(), nullable=False),
        sa.Column("egress_authorization_snapshot_id", ident),
        sa.Column("request_payload_ref", ident),
        sa.Column("request_payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("retrieval_run_ref", ident),
        sa.Column("context_bundle_fingerprint", sa.LargeBinary()),
        sa.Column("invocation_state", sa.Text(), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("schema_validation_required", sa.Boolean(), nullable=False),
        sa.Column("schema_validation_state", sa.Text(), nullable=False),
        sa.Column("suggestion_payload_ref", ident),
        sa.Column("response_fingerprint", sa.LargeBinary()),
        sa.Column("usage_input_tokens", sa.BigInteger()),
        sa.Column("usage_output_tokens", sa.BigInteger()),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.Column("provider_request_ref", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("retryable", sa.Boolean()),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("started_at", timestamp),
        sa.Column("completed_at", timestamp),
        sa.ForeignKeyConstraint(["ai_task_id"], ["plm.ai_tasks.ai_task_id"],
                                name="fk_ai_invocations__task", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_invocations__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_invocations__provider_config", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"],
                                name="fk_ai_invocations__model", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["prompt_template_id", "prompt_version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_invocations__prompt_version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["egress_authorization_snapshot_id", "ai_task_id"],
            ["plm.ai_egress_authorization_snapshots.egress_authorization_snapshot_id",
             "plm.ai_egress_authorization_snapshots.ai_task_id"],
            name="fk_ai_invocations__egress_task", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_task_id", "attempt_no", name="uq_ai_invocations__task_attempt"),
        sa.UniqueConstraint("ai_invocation_id", "ai_task_id",
                            name="uq_ai_invocations__identity_task"),
        sa.CheckConstraint(
            "ai_invocation_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_task_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_model_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_invocations__ids"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_ai_invocations__scope"),
        sa.CheckConstraint(
            "attempt_no BETWEEN 1 AND 2147483647 AND prompt_version_no>0 AND schema_version>0 "
            "AND lock_version>=0 AND octet_length(input_fingerprint)=32 "
            "AND octet_length(request_payload_fingerprint)=32 "
            "AND (response_fingerprint IS NULL OR octet_length(response_fingerprint)=32) "
            "AND (context_bundle_fingerprint IS NULL OR octet_length(context_bundle_fingerprint)=32)",
            name="ck_ai_invocations__version_fingerprint"),
        sa.CheckConstraint(
            "model_revision_observed ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' "
            "AND output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND (provider_request_ref IS NULL OR (char_length(provider_request_ref) BETWEEN 1 AND 255 "
            "AND provider_request_ref !~ '[\\r\\n]'))",
            name="ck_ai_invocations__refs"),
        sa.CheckConstraint(
            "(egress_authorization_mode='AUTHORIZED' AND egress_authorization_snapshot_id IS NOT NULL) OR "
            "(egress_authorization_mode='NOT_APPLICABLE' AND egress_authorization_snapshot_id IS NULL)",
            name="ck_ai_invocations__egress"),
        sa.CheckConstraint(
            "invocation_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED') "
            "AND schema_validation_state IN ('NOT_APPLICABLE','PENDING','VALID','INVALID') "
            "AND ((schema_validation_required AND schema_validation_state<>'NOT_APPLICABLE') "
            "OR (NOT schema_validation_required AND schema_validation_state='NOT_APPLICABLE'))",
            name="ck_ai_invocations__state"),
        sa.CheckConstraint(
            "(invocation_state NOT IN ('SUCCEEDED','FAILED','CANCELLED') AND completed_at IS NULL) OR "
            "(invocation_state IN ('SUCCEEDED','FAILED','CANCELLED') AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) "
            "AND (invocation_state<>'SUCCEEDED' OR (response_fingerprint IS NOT NULL "
            "AND ((schema_validation_required AND schema_validation_state='VALID') "
            "OR (NOT schema_validation_required AND schema_validation_state='NOT_APPLICABLE')))) "
            "AND (invocation_state<>'FAILED' OR (error_code IS NOT NULL AND retryable IS NOT NULL))",
            name="ck_ai_invocations__terminal"),
        sa.CheckConstraint(
            "(suggestion_payload_ref IS NULL OR (invocation_state='SUCCEEDED' "
            "AND schema_validation_state='VALID')) "
            "AND (error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (usage_input_tokens IS NULL OR usage_input_tokens>=0) "
            "AND (usage_output_tokens IS NULL OR usage_output_tokens>=0) "
            "AND (latency_ms IS NULL OR latency_ms>=0)",
            name="ck_ai_invocations__result"),
        sa.CheckConstraint(
            "(started_at IS NULL OR started_at>=created_at) "
            "AND (completed_at IS NULL OR completed_at>=started_at) "
            "AND isfinite(created_at) AND (started_at IS NULL OR isfinite(started_at)) "
            "AND (completed_at IS NULL OR isfinite(completed_at))",
            name="ck_ai_invocations__time"),
        schema="plm",
    )
    op.create_index("ix_ai_invocations__task_state", "ai_invocations",
                    ["ai_task_id", "invocation_state", "attempt_no"], schema="plm")
    op.create_index("ix_ai_invocations__provider_time", "ai_invocations",
                    ["ai_provider_id", "created_at"], schema="plm")

    op.create_table(
        "ai_invocation_context_refs",
        sa.Column("context_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("ai_invocation_id", ident, nullable=False),
        sa.Column("ref_ordinal", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("owner_module", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("version_id", ident, nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("added_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["ai_invocation_id"], ["plm.ai_invocations.ai_invocation_id"],
                                name="fk_ai_invocation_contexts__invocation", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_invocation_contexts__project", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_invocation_id", "ref_ordinal",
                            name="uq_ai_invocation_contexts__ordinal"),
        sa.CheckConstraint(
            "context_ref_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_invocation_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ref_ordinal BETWEEN 1 AND 10000", name="ck_ai_invocation_contexts__ids"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_ai_invocation_contexts__scope"),
        sa.CheckConstraint(
            "owner_module ~ '^[a-z][a-z0-9_]{0,63}$' "
            "AND object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' "
            "AND octet_length(content_fingerprint)=32 AND isfinite(added_at)",
            name="ck_ai_invocation_contexts__ref"),
        schema="plm",
    )
    op.create_index("ix_ai_invocation_contexts__version", "ai_invocation_context_refs",
                    ["owner_module", "object_type", "version_id"], schema="plm")

    op.add_column("ai_tasks", sa.Column("current_invocation_ref", ident), schema="plm")
    op.create_foreign_key(
        "fk_ai_tasks__current_invocation", "ai_tasks", "ai_invocations",
        ["current_invocation_ref", "ai_task_id"], ["ai_invocation_id", "ai_task_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )

    op.execute(r"""
        CREATE FUNCTION plm.guard_ai_egress_snapshot()
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
        CREATE TRIGGER trg_ai_egress_snapshot_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_egress_authorization_snapshots
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_egress_snapshot();

        CREATE FUNCTION plm.guard_ai_invocation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_scope text; parent_project uuid; parent_state text;
                parent_input bytea; parent_task_type text; expected_attempt integer;
                v_model_provider uuid; v_model_revision text; v_model_state text;
                v_provider_state text; v_config_egress text;
                v_template_state text; v_active_version bigint; v_template_task_type text;
                v_prompt_schema text; v_prompt_schema_version bigint;
                snapshot_provider uuid; snapshot_config uuid;
                snapshot_start timestamptz; snapshot_end timestamptz;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'AI Invocation history cannot be deleted';
            END IF;
            IF TG_OP='UPDATE' THEN
                IF OLD.invocation_state IN ('SUCCEEDED','FAILED','CANCELLED') THEN
                    RAISE EXCEPTION 'terminal AI Invocation is immutable';
                END IF;
                IF (NEW.ai_invocation_id, NEW.ai_task_id, NEW.attempt_no, NEW.scope, NEW.project_id,
                    NEW.ai_provider_id, NEW.provider_config_version_id, NEW.ai_model_id,
                    NEW.model_revision_observed, NEW.prompt_template_id, NEW.prompt_version_no,
                    NEW.output_schema_ref, NEW.schema_version, NEW.input_fingerprint,
                    NEW.egress_authorization_mode, NEW.egress_authorization_snapshot_id,
                    NEW.request_payload_ref, NEW.request_payload_fingerprint, NEW.retrieval_run_ref,
                    NEW.context_bundle_fingerprint, NEW.schema_validation_required, NEW.created_at)
                   IS DISTINCT FROM
                   (OLD.ai_invocation_id, OLD.ai_task_id, OLD.attempt_no, OLD.scope, OLD.project_id,
                    OLD.ai_provider_id, OLD.provider_config_version_id, OLD.ai_model_id,
                    OLD.model_revision_observed, OLD.prompt_template_id, OLD.prompt_version_no,
                    OLD.output_schema_ref, OLD.schema_version, OLD.input_fingerprint,
                    OLD.egress_authorization_mode, OLD.egress_authorization_snapshot_id,
                    OLD.request_payload_ref, OLD.request_payload_fingerprint, OLD.retrieval_run_ref,
                    OLD.context_bundle_fingerprint, OLD.schema_validation_required, OLD.created_at) THEN
                    RAISE EXCEPTION 'AI Invocation identity and request snapshot are immutable';
                END IF;
                IF NEW.lock_version<>OLD.lock_version+1 THEN
                    RAISE EXCEPTION 'AI Invocation lock version must advance once';
                END IF;
                IF (OLD.invocation_state='PENDING' AND NEW.invocation_state NOT IN
                    ('PENDING','RUNNING','FAILED','CANCELLED')) OR
                   (OLD.invocation_state='RUNNING' AND NEW.invocation_state NOT IN
                    ('RUNNING','SUCCEEDED','FAILED','CANCELLED')) THEN
                    RAISE EXCEPTION 'invalid AI Invocation state transition';
                END IF;
                RETURN NEW;
            END IF;

            SELECT scope, project_id, task_state, input_fingerprint, task_type
              INTO parent_scope, parent_project, parent_state, parent_input, parent_task_type
              FROM plm.ai_tasks WHERE ai_task_id=NEW.ai_task_id FOR UPDATE;
            IF NOT FOUND OR NEW.scope IS DISTINCT FROM parent_scope
               OR NEW.project_id IS DISTINCT FROM parent_project
               OR NEW.input_fingerprint IS DISTINCT FROM parent_input
               OR parent_state NOT IN ('QUEUED','RUNNING') THEN
                RAISE EXCEPTION 'AI Invocation task snapshot mismatch';
            END IF;
            SELECT coalesce(max(attempt_no),0)+1 INTO expected_attempt
              FROM plm.ai_invocations WHERE ai_task_id=NEW.ai_task_id;
            IF NEW.attempt_no<>expected_attempt OR NEW.invocation_state<>'PENDING' THEN
                RAISE EXCEPTION 'AI Invocation must start as the next PENDING attempt';
            END IF;
            SELECT m.ai_provider_id, m.model_revision, m.model_state
              INTO v_model_provider, v_model_revision, v_model_state
              FROM plm.ai_models m WHERE m.ai_model_id=NEW.ai_model_id;
            IF NOT FOUND OR v_model_provider<>NEW.ai_provider_id OR v_model_state<>'AVAILABLE'
               OR v_model_revision<>NEW.model_revision_observed THEN
                RAISE EXCEPTION 'AI Invocation model snapshot is not available';
            END IF;
            SELECT p.provider_state, c.egress_class INTO v_provider_state, v_config_egress
              FROM plm.ai_providers p JOIN plm.ai_provider_config_versions c
                ON c.ai_provider_id=p.ai_provider_id
             WHERE p.ai_provider_id=NEW.ai_provider_id
               AND c.provider_config_version_id=NEW.provider_config_version_id;
            IF NOT FOUND OR v_provider_state<>'ACTIVE' THEN
                RAISE EXCEPTION 'AI Invocation provider is not active';
            END IF;
            SELECT t.template_state, t.active_version_no, t.task_type,
                   v.output_schema_ref, v.schema_version
              INTO v_template_state, v_active_version, v_template_task_type,
                   v_prompt_schema, v_prompt_schema_version
              FROM plm.ai_prompt_templates t JOIN plm.ai_prompt_versions v
                ON v.prompt_template_id=t.prompt_template_id
               AND v.version_no=NEW.prompt_version_no
             WHERE t.prompt_template_id=NEW.prompt_template_id;
            IF NOT FOUND OR v_template_state<>'ACTIVE' OR v_active_version<>NEW.prompt_version_no
               OR v_template_task_type<>parent_task_type
               OR v_prompt_schema<>NEW.output_schema_ref
               OR v_prompt_schema_version<>NEW.schema_version THEN
                RAISE EXCEPTION 'AI Invocation Prompt version is not currently active';
            END IF;
            IF NEW.egress_authorization_mode='AUTHORIZED' THEN
                SELECT ai_provider_id, provider_config_version_id, approved_at, valid_until
                  INTO snapshot_provider, snapshot_config, snapshot_start, snapshot_end
                  FROM plm.ai_egress_authorization_snapshots
                 WHERE egress_authorization_snapshot_id=NEW.egress_authorization_snapshot_id
                   AND ai_task_id=NEW.ai_task_id;
                IF NOT FOUND OR snapshot_provider<>NEW.ai_provider_id
                   OR snapshot_config<>NEW.provider_config_version_id
                   OR NOT (snapshot_start<=NEW.created_at AND NEW.created_at<snapshot_end) THEN
                    RAISE EXCEPTION 'AI Invocation egress authorization is invalid';
                END IF;
            ELSIF v_config_egress NOT IN ('INTERNAL','NO_EGRESS') THEN
                RAISE EXCEPTION 'external AI Invocation requires authorization';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER trg_ai_invocation_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_invocations
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_invocation();

        CREATE FUNCTION plm.guard_ai_invocation_context()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_scope text; parent_project uuid; parent_state text;
        BEGIN
            IF TG_OP<>'INSERT' THEN
                RAISE EXCEPTION 'AI Invocation context history is immutable';
            END IF;
            SELECT scope, project_id, invocation_state
              INTO parent_scope, parent_project, parent_state
              FROM plm.ai_invocations WHERE ai_invocation_id=NEW.ai_invocation_id FOR KEY SHARE;
            IF NOT FOUND OR NEW.scope IS DISTINCT FROM parent_scope
               OR NEW.project_id IS DISTINCT FROM parent_project OR parent_state<>'PENDING' THEN
                RAISE EXCEPTION 'AI Invocation context scope or state mismatch';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER trg_ai_invocation_context_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_invocation_context_refs
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_invocation_context();

        CREATE FUNCTION plm.guard_ai_invocation_history_truncate()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AI Invocation history cannot be truncated';
        END; $$;
        CREATE TRIGGER trg_ai_egress_snapshot_no_truncate
        BEFORE TRUNCATE ON plm.ai_egress_authorization_snapshots
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_invocation_history_truncate();
        CREATE TRIGGER trg_ai_invocation_no_truncate BEFORE TRUNCATE ON plm.ai_invocations
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_invocation_history_truncate();
        CREATE TRIGGER trg_ai_invocation_context_no_truncate
        BEFORE TRUNCATE ON plm.ai_invocation_context_refs
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_invocation_history_truncate();

        CREATE OR REPLACE FUNCTION plm.guard_ai_task_identity()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE latest_invocation uuid;
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
            IF NEW.current_invocation_ref IS DISTINCT FROM OLD.current_invocation_ref THEN
                IF NEW.current_invocation_ref IS NULL THEN
                    RAISE EXCEPTION 'AI Task current Invocation cannot be cleared';
                END IF;
                SELECT ai_invocation_id INTO latest_invocation FROM plm.ai_invocations
                 WHERE ai_task_id=NEW.ai_task_id ORDER BY attempt_no DESC LIMIT 1;
                IF latest_invocation IS DISTINCT FROM NEW.current_invocation_ref THEN
                    RAISE EXCEPTION 'AI Task current Invocation must be the latest attempt';
                END IF;
            END IF;
            RETURN NEW;
        END; $$;
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Invocation downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.ai_invocation_context_refs, plm.ai_invocations, "
        "plm.ai_egress_authorization_snapshots, plm.ai_tasks IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_invocation_context_refs)
               OR EXISTS (SELECT 1 FROM plm.ai_invocations)
               OR EXISTS (SELECT 1 FROM plm.ai_egress_authorization_snapshots)
               OR EXISTS (SELECT 1 FROM plm.ai_tasks WHERE current_invocation_ref IS NOT NULL) THEN
                RAISE EXCEPTION 'AI Invocation history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("""
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
    """)
    op.drop_constraint("fk_ai_tasks__current_invocation", "ai_tasks",
                       schema="plm", type_="foreignkey")
    op.drop_column("ai_tasks", "current_invocation_ref", schema="plm")
    op.execute("DROP TRIGGER trg_ai_invocation_context_no_truncate ON plm.ai_invocation_context_refs")
    op.execute("DROP TRIGGER trg_ai_invocation_no_truncate ON plm.ai_invocations")
    op.execute("DROP TRIGGER trg_ai_egress_snapshot_no_truncate ON plm.ai_egress_authorization_snapshots")
    op.execute("DROP TRIGGER trg_ai_invocation_context_guard ON plm.ai_invocation_context_refs")
    op.execute("DROP TRIGGER trg_ai_invocation_guard ON plm.ai_invocations")
    op.execute("DROP TRIGGER trg_ai_egress_snapshot_guard ON plm.ai_egress_authorization_snapshots")
    op.execute("DROP FUNCTION plm.guard_ai_invocation_history_truncate()")
    op.execute("DROP FUNCTION plm.guard_ai_invocation_context()")
    op.execute("DROP FUNCTION plm.guard_ai_invocation()")
    op.execute("DROP FUNCTION plm.guard_ai_egress_snapshot()")
    op.drop_index("ix_ai_invocation_contexts__version",
                  table_name="ai_invocation_context_refs", schema="plm")
    op.drop_table("ai_invocation_context_refs", schema="plm")
    op.drop_index("ix_ai_invocations__provider_time", table_name="ai_invocations", schema="plm")
    op.drop_index("ix_ai_invocations__task_state", table_name="ai_invocations", schema="plm")
    op.drop_table("ai_invocations", schema="plm")
    op.drop_index("ix_ai_egress_snapshots__task_time",
                  table_name="ai_egress_authorization_snapshots", schema="plm")
    op.drop_table("ai_egress_authorization_snapshots", schema="plm")
