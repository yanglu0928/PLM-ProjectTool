"""Persist immutable AI execution Content Plans and exact source identities.

Revision ID: 20261003_0072
Revises: 20261003_0071
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261003_0072"
down_revision = "20261003_0071"
branch_labels = None
depends_on = None


_TASK_TYPES = (
    "'DOCUMENT_PARSE','CAPABILITY_EXTRACT','GAP_ANALYSIS','SURVEY_GENERATE',"
    "'SURVEY_ANALYZE','REQUIREMENT_NORMALIZE','REQUIREMENT_MATCH',"
    "'SOLUTION_SUGGEST','PROTOTYPE_GENERATE','SOLUTION_GENERATE',"
    "'PLAN_GENERATE','OUTPUT_SUMMARIZE'"
)


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)

    op.create_table(
        "ai_execution_content_plans",
        sa.Column("content_plan_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("egress_preview_id", ident, nullable=False),
        sa.Column("content_plan_version", sa.BigInteger(), nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("purpose_ref", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("source_refs_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("prompt_policy_ref", sa.Text(), nullable=False),
        sa.Column("prompt_policy_version", sa.BigInteger(), nullable=False),
        sa.Column("prompt_template_id", ident, nullable=False),
        sa.Column("prompt_version_no", sa.BigInteger(), nullable=False),
        sa.Column("system_template_hash", sa.Text(), nullable=False),
        sa.Column("user_template_hash", sa.Text(), nullable=False),
        sa.Column("provider_policy_ref", sa.Text(), nullable=False),
        sa.Column("output_schema_ref", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.BigInteger(), nullable=False),
        sa.Column("rendering_policy_ref", sa.Text(), nullable=False),
        sa.Column("rendering_policy_version", sa.BigInteger(), nullable=False),
        sa.Column("task_parameters_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("context_policy_ref", sa.Text(), nullable=False),
        sa.Column("context_mode", sa.Text(), nullable=False),
        sa.Column("retrieval_run_id", ident),
        sa.Column("context_bundle_id", ident),
        sa.Column("context_bundle_fingerprint", sa.LargeBinary()),
        sa.Column("context_record_count", sa.BigInteger(), nullable=False),
        sa.Column("context_content_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_config_version_id", ident, nullable=False),
        sa.Column("ai_model_id", ident, nullable=False),
        sa.Column("provider_model_key", sa.Text(), nullable=False),
        sa.Column("model_revision", sa.Text(), nullable=False),
        sa.Column("data_region", sa.Text(), nullable=False),
        sa.Column("allowed_data_categories", postgresql.JSONB(), nullable=False),
        sa.Column("minimal_payload_policy_ref", sa.Text(), nullable=False),
        sa.Column("envelope_encoding_ref", sa.Text(), nullable=False),
        sa.Column("envelope_encoding_version", sa.BigInteger(), nullable=False),
        sa.Column("token_estimator_ref", sa.Text(), nullable=False),
        sa.Column("token_estimator_version", sa.BigInteger(), nullable=False),
        sa.Column("content_plan_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("record_count", sa.BigInteger(), nullable=False),
        sa.Column("payload_bytes", sa.BigInteger(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["egress_preview_id"], ["plm.ai_egress_previews.egress_preview_id"],
            name="fk_ai_content_plans__preview", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_ai_content_plans__project", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_id", "prompt_version_no"],
            ["plm.ai_prompt_versions.prompt_template_id",
             "plm.ai_prompt_versions.version_no"],
            name="fk_ai_content_plans__prompt_version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_content_plans__provider_config", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["ai_model_id"], ["plm.ai_models.ai_model_id"],
            name="fk_ai_content_plans__model", ondelete="NO ACTION",
        ),
        sa.UniqueConstraint("egress_preview_id", name="uq_ai_content_plans__preview"),
        sa.CheckConstraint(
            _nonzero("content_plan_id", "egress_preview_id", "project_id",
                     "prompt_template_id", "ai_provider_id",
                     "provider_config_version_id", "ai_model_id"),
            name="ck_ai_content_plans__uuid",
        ),
        sa.CheckConstraint(
            "content_plan_version=1 AND prompt_policy_version BETWEEN 1 AND 2147483647 "
            "AND prompt_version_no BETWEEN 1 AND 9223372036854775807 "
            "AND schema_version BETWEEN 1 AND 2147483647 "
            "AND rendering_policy_version BETWEEN 1 AND 2147483647 "
            "AND envelope_encoding_version BETWEEN 1 AND 2147483647 "
            "AND token_estimator_version BETWEEN 1 AND 2147483647",
            name="ck_ai_content_plans__versions",
        ),
        sa.CheckConstraint(f"task_type IN ({_TASK_TYPES})",
                           name="ck_ai_content_plans__task_type"),
        sa.CheckConstraint(
            "purpose_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND prompt_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND provider_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND rendering_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND context_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND minimal_payload_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND envelope_encoding_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND token_estimator_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_ai_content_plans__refs",
        ),
        sa.CheckConstraint(
            "provider_model_key ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' "
            "AND model_revision ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' "
            "AND data_region ~ '^[a-z][a-z0-9-]{0,63}$' "
            "AND system_template_hash ~ '^[0-9a-f]{64}$' "
            "AND user_template_hash ~ '^[0-9a-f]{64}$'",
            name="ck_ai_content_plans__route_hashes",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_data_categories)='array' "
            "AND jsonb_array_length(allowed_data_categories) BETWEEN 1 AND 64",
            name="ck_ai_content_plans__categories",
        ),
        sa.CheckConstraint(
            "octet_length(source_refs_fingerprint)=32 "
            "AND octet_length(task_parameters_fingerprint)=32 "
            "AND octet_length(content_plan_fingerprint)=32 "
            "AND octet_length(payload_fingerprint)=32",
            name="ck_ai_content_plans__fingerprints",
        ),
        sa.CheckConstraint(
            "(context_mode='NONE' AND retrieval_run_id IS NULL "
            "AND context_bundle_id IS NULL AND context_bundle_fingerprint IS NULL "
            "AND context_record_count=0 AND context_content_size_bytes=0) OR "
            "(context_mode='RAG_CONTEXT' AND retrieval_run_id IS NOT NULL "
            "AND context_bundle_id IS NOT NULL "
            "AND octet_length(context_bundle_fingerprint)=32 "
            "AND context_record_count BETWEEN 1 AND 1000000000 "
            "AND context_content_size_bytes BETWEEN 1 AND 1073741824)",
            name="ck_ai_content_plans__context",
        ),
        sa.CheckConstraint(
            "record_count BETWEEN 1 AND 1000000000 "
            "AND payload_bytes BETWEEN 1 AND 100000000 "
            "AND input_tokens BETWEEN 1 AND 1073741824 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_ai_content_plans__metrics",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_ai_content_plans__project_time", "ai_execution_content_plans",
        ["project_id", sa.text("created_at DESC"), sa.text("content_plan_id DESC")],
        schema="plm",
    )
    op.create_index(
        "ix_ai_content_plans__prompt_version", "ai_execution_content_plans",
        ["prompt_template_id", "prompt_version_no"], schema="plm",
    )

    op.create_table(
        "ai_execution_content_sources",
        sa.Column("content_source_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("content_plan_id", ident, nullable=False),
        sa.Column("source_ordinal", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("owner_module", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", ident, nullable=False),
        sa.Column("version_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("content_kind", sa.Text(), nullable=False),
        sa.Column("content_revision_id", ident, nullable=False),
        sa.Column("content_object_id", ident, nullable=False),
        sa.Column("producer_ref", sa.Text(), nullable=False),
        sa.Column("producer_version", sa.Text(), nullable=False),
        sa.Column("content_schema_ref", sa.Text(), nullable=False),
        sa.Column("selection_policy_ref", sa.Text(), nullable=False),
        sa.Column("source_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("projection_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("content_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("record_count", sa.BigInteger(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["content_plan_id"], ["plm.ai_execution_content_plans.content_plan_id"],
            name="fk_ai_content_sources__plan", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_ai_content_sources__project", ondelete="NO ACTION",
        ),
        sa.UniqueConstraint("content_plan_id", "source_ordinal",
                            name="uq_ai_content_sources__ordinal"),
        sa.UniqueConstraint(
            "content_plan_id", "resource_type", "owner_module", "object_type",
            "object_id", "version_id", name="uq_ai_content_sources__semantic",
        ),
        sa.CheckConstraint(
            _nonzero("content_source_id", "content_plan_id", "project_id", "object_id",
                     "version_id", "content_revision_id", "content_object_id"),
            name="ck_ai_content_sources__uuid",
        ),
        sa.CheckConstraint(
            "source_ordinal BETWEEN 1 AND 1000 "
            "AND resource_type ~ '^[A-Z][A-Z0-9-]{0,63}$' "
            "AND owner_module ~ '^[a-z][a-z0-9_]{0,63}$' "
            "AND object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' "
            "AND content_kind ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name="ck_ai_content_sources__shape",
        ),
        sa.CheckConstraint(
            "producer_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND producer_version ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' "
            "AND content_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND selection_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_ai_content_sources__refs",
        ),
        sa.CheckConstraint(
            "octet_length(source_fingerprint)=32 "
            "AND octet_length(content_fingerprint)=32 "
            "AND octet_length(projection_fingerprint)=32",
            name="ck_ai_content_sources__fingerprints",
        ),
        sa.CheckConstraint(
            "content_size_bytes BETWEEN 1 AND 1073741824 "
            "AND record_count BETWEEN 1 AND 1000000000 "
            "AND isfinite(created_at)",
            name="ck_ai_content_sources__metrics",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_ai_content_sources__content_identity", "ai_execution_content_sources",
        ["owner_module", "content_kind", "content_revision_id", "content_object_id"],
        schema="plm",
    )

    for table, foreign_key, index in (
        ("ai_egress_authorizations", "fk_ai_egress_authorizations__content_plan",
         "ix_ai_egress_authorizations__content_plan"),
        ("ai_tasks", "fk_ai_tasks__content_plan", "ix_ai_tasks__content_plan"),
        ("ai_egress_authorization_snapshots", "fk_ai_egress_snapshots__content_plan",
         "ix_ai_egress_snapshots__content_plan"),
        ("ai_invocations", "fk_ai_invocations__content_plan",
         "ix_ai_invocations__content_plan"),
    ):
        op.add_column(table, sa.Column("content_plan_ref", ident), schema="plm")
        op.create_foreign_key(
            foreign_key, table, "ai_execution_content_plans",
            ["content_plan_ref"], ["content_plan_id"],
            source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        )
        op.create_index(index, table, ["content_plan_ref"], schema="plm")

    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI Content Plan downgrade is disabled")
    linked_tables = (
        "ai_invocations", "ai_egress_authorization_snapshots",
        "ai_tasks", "ai_egress_authorizations",
    )
    op.execute(
        "LOCK TABLE plm.ai_execution_content_sources, "
        "plm.ai_execution_content_plans, "
        + ", ".join("plm." + table for table in linked_tables)
        + " IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_execution_content_plans)
               OR EXISTS (SELECT 1 FROM plm.ai_execution_content_sources)
               OR EXISTS (SELECT 1 FROM plm.ai_egress_authorizations
                           WHERE content_plan_ref IS NOT NULL)
               OR EXISTS (SELECT 1 FROM plm.ai_tasks
                           WHERE content_plan_ref IS NOT NULL)
               OR EXISTS (SELECT 1 FROM plm.ai_egress_authorization_snapshots
                           WHERE content_plan_ref IS NOT NULL)
               OR EXISTS (SELECT 1 FROM plm.ai_invocations
                           WHERE content_plan_ref IS NOT NULL)
            THEN
                RAISE EXCEPTION 'AI Content Plan history prevents downgrade';
            END IF;
        END $$;
    """)
    for table in linked_tables:
        op.execute(
            f"DROP TRIGGER trg_{table}__content_plan_ref_immutable ON plm.{table}"
        )
    op.execute("DROP FUNCTION plm.guard_ai_content_plan_ref_immutable()")
    op.execute(
        "DROP TRIGGER trg_ai_content_source_completeness "
        "ON plm.ai_execution_content_sources"
    )
    op.execute(
        "DROP TRIGGER trg_ai_content_plan_completeness "
        "ON plm.ai_execution_content_plans"
    )
    op.execute("DROP FUNCTION plm.assert_ai_content_plan_complete()")
    op.execute(
        "DROP TRIGGER trg_ai_content_source_no_truncate "
        "ON plm.ai_execution_content_sources"
    )
    op.execute(
        "DROP TRIGGER trg_ai_content_plan_no_truncate "
        "ON plm.ai_execution_content_plans"
    )
    op.execute("DROP FUNCTION plm.guard_ai_content_plan_truncate()")
    op.execute(
        "DROP TRIGGER trg_ai_preview_source_after_plan "
        "ON plm.ai_egress_preview_source_refs"
    )
    op.execute("DROP FUNCTION plm.guard_ai_preview_source_after_plan()")
    op.execute(
        "DROP TRIGGER trg_ai_content_source_guard "
        "ON plm.ai_execution_content_sources"
    )
    op.execute(
        "DROP TRIGGER trg_ai_content_plan_guard "
        "ON plm.ai_execution_content_plans"
    )
    op.execute("DROP FUNCTION plm.guard_ai_content_source()")
    op.execute("DROP FUNCTION plm.guard_ai_content_plan()")

    for table, foreign_key, index in (
        ("ai_invocations", "fk_ai_invocations__content_plan",
         "ix_ai_invocations__content_plan"),
        ("ai_egress_authorization_snapshots", "fk_ai_egress_snapshots__content_plan",
         "ix_ai_egress_snapshots__content_plan"),
        ("ai_tasks", "fk_ai_tasks__content_plan", "ix_ai_tasks__content_plan"),
        ("ai_egress_authorizations", "fk_ai_egress_authorizations__content_plan",
         "ix_ai_egress_authorizations__content_plan"),
    ):
        op.drop_index(index, table_name=table, schema="plm")
        op.drop_constraint(foreign_key, table, schema="plm", type_="foreignkey")
        op.drop_column(table, "content_plan_ref", schema="plm")

    op.drop_index(
        "ix_ai_content_sources__content_identity",
        table_name="ai_execution_content_sources", schema="plm",
    )
    op.drop_table("ai_execution_content_sources", schema="plm")
    op.drop_index(
        "ix_ai_content_plans__prompt_version",
        table_name="ai_execution_content_plans", schema="plm",
    )
    op.drop_index(
        "ix_ai_content_plans__project_time",
        table_name="ai_execution_content_plans", schema="plm",
    )
    op.drop_table("ai_execution_content_plans", schema="plm")


def _nonzero(*columns: str) -> str:
    return " AND ".join(
        f"{column}<>'00000000-0000-0000-0000-000000000000'::uuid"
        for column in columns
    )


_GUARDS = r"""
CREATE FUNCTION plm.guard_ai_content_plan()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    preview plm.ai_egress_previews%ROWTYPE;
    template_task_type text;
    version_row plm.ai_prompt_versions%ROWTYPE;
    observed_model_provider uuid;
    observed_model_key text;
    observed_model_revision text;
    category jsonb;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'AI Content Plan history is immutable';
    END IF;
    SELECT * INTO preview FROM plm.ai_egress_previews
     WHERE egress_preview_id=NEW.egress_preview_id FOR KEY SHARE;
    IF NOT FOUND OR preview.operation_type<>'AI_TASK'
       OR preview.scope<>'PROJECT'
       OR ROW(NEW.project_id,NEW.purpose_ref,NEW.source_refs_fingerprint,
              NEW.ai_provider_id,NEW.provider_config_version_id,NEW.ai_model_id,
              NEW.data_region,NEW.allowed_data_categories,
              NEW.minimal_payload_policy_ref,NEW.payload_fingerprint,
              NEW.record_count)
          IS DISTINCT FROM
          ROW(preview.project_id,preview.purpose_ref,preview.source_refs_fingerprint,
              preview.ai_provider_id,preview.provider_config_version_id,
              preview.ai_model_id,preview.data_region,
              preview.allowed_data_categories,preview.minimal_payload_policy_ref,
              preview.payload_fingerprint,preview.estimated_record_count)
       OR NEW.payload_bytes>preview.max_payload_bytes
       OR NEW.input_tokens>preview.max_input_tokens
    THEN
        RAISE EXCEPTION 'AI Content Plan does not match Preview';
    END IF;
    SELECT task_type INTO template_task_type FROM plm.ai_prompt_templates
     WHERE prompt_template_id=NEW.prompt_template_id FOR KEY SHARE;
    SELECT * INTO version_row FROM plm.ai_prompt_versions
     WHERE prompt_template_id=NEW.prompt_template_id
       AND version_no=NEW.prompt_version_no FOR KEY SHARE;
    IF template_task_type IS DISTINCT FROM NEW.task_type
       OR version_row.prompt_template_id IS NULL
       OR ROW(version_row.system_template_hash,version_row.user_template_hash,
              version_row.output_schema_ref,version_row.schema_version,
              version_row.rag_policy_ref,version_row.provider_policy_ref)
          IS DISTINCT FROM
          ROW(NEW.system_template_hash,NEW.user_template_hash,
              NEW.output_schema_ref,NEW.schema_version,
              NEW.context_policy_ref,NEW.provider_policy_ref)
    THEN
        RAISE EXCEPTION 'AI Content Plan Prompt identity mismatch';
    END IF;
    SELECT m.ai_provider_id,m.provider_model_key,m.model_revision
      INTO observed_model_provider,observed_model_key,observed_model_revision
      FROM plm.ai_models m WHERE m.ai_model_id=NEW.ai_model_id FOR KEY SHARE;
    IF observed_model_provider IS DISTINCT FROM NEW.ai_provider_id
       OR observed_model_key IS DISTINCT FROM NEW.provider_model_key
       OR observed_model_revision IS DISTINCT FROM NEW.model_revision THEN
        RAISE EXCEPTION 'AI Content Plan model identity mismatch';
    END IF;
    FOR category IN SELECT value FROM jsonb_array_elements(NEW.allowed_data_categories)
    LOOP
        IF jsonb_typeof(category)<>'string'
           OR (category#>>'{}') !~ '^[A-Z][A-Z0-9_]{0,63}$' THEN
            RAISE EXCEPTION 'AI Content Plan category is invalid';
        END IF;
    END LOOP;
    IF (SELECT count(*)<>count(DISTINCT value)
          FROM jsonb_array_elements(NEW.allowed_data_categories))
       OR NEW.allowed_data_categories IS DISTINCT FROM (
            SELECT jsonb_agg(value ORDER BY value)
              FROM jsonb_array_elements(NEW.allowed_data_categories)
       )
    THEN
        RAISE EXCEPTION 'AI Content Plan categories must be unique and ordered';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_content_plan_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_execution_content_plans
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_content_plan();

CREATE FUNCTION plm.guard_ai_content_source()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    plan_project uuid;
    plan_preview uuid;
    plan_xid bigint;
    preview_source plm.ai_egress_preview_source_refs%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'AI Content Source history is immutable';
    END IF;
    SELECT project_id,egress_preview_id,created_xid
      INTO plan_project,plan_preview,plan_xid
      FROM plm.ai_execution_content_plans
     WHERE content_plan_id=NEW.content_plan_id FOR KEY SHARE;
    IF NOT FOUND OR plan_project IS DISTINCT FROM NEW.project_id
       OR plan_xid IS DISTINCT FROM txid_current() THEN
        RAISE EXCEPTION 'AI Content Source must be created with its Plan';
    END IF;
    SELECT * INTO preview_source FROM plm.ai_egress_preview_source_refs
     WHERE egress_preview_id=plan_preview AND ref_ordinal=NEW.source_ordinal
     FOR KEY SHARE;
    IF NOT FOUND OR
       ROW(preview_source.resource_type,preview_source.owner_module,
           preview_source.object_type,preview_source.object_id,
           preview_source.version_id,preview_source.project_id)
       IS DISTINCT FROM
       ROW(NEW.resource_type,NEW.owner_module,NEW.object_type,NEW.object_id,
           NEW.version_id,NEW.project_id)
    THEN
        RAISE EXCEPTION 'AI Content Source does not match Preview source';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_content_source_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_execution_content_sources
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_content_source();

CREATE FUNCTION plm.guard_ai_preview_source_after_plan()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM plm.ai_execution_content_plans
         WHERE egress_preview_id=NEW.egress_preview_id
    ) THEN
        RAISE EXCEPTION 'AI Preview sources are frozen by Content Plan';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_preview_source_after_plan
BEFORE INSERT ON plm.ai_egress_preview_source_refs
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_preview_source_after_plan();

CREATE FUNCTION plm.guard_ai_content_plan_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'AI Content Plan history cannot be truncated';
END; $$;

CREATE TRIGGER trg_ai_content_plan_no_truncate
BEFORE TRUNCATE ON plm.ai_execution_content_plans
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_content_plan_truncate();
CREATE TRIGGER trg_ai_content_source_no_truncate
BEFORE TRUNCATE ON plm.ai_execution_content_sources
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_content_plan_truncate();

CREATE FUNCTION plm.assert_ai_content_plan_complete()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    target_plan uuid;
    planned_count bigint;
    planned_records bigint;
    preview_count bigint;
    context_records bigint;
BEGIN
    target_plan:=COALESCE(NEW.content_plan_id,OLD.content_plan_id);
    SELECT count(*),COALESCE(sum(record_count),0),COALESCE(max(source_ordinal),0)
      INTO planned_count,planned_records,preview_count
      FROM plm.ai_execution_content_sources
     WHERE content_plan_id=target_plan;
    SELECT context_record_count INTO context_records
      FROM plm.ai_execution_content_plans WHERE content_plan_id=target_plan;
    IF NOT FOUND THEN RETURN NULL; END IF;
    IF planned_count<1 OR planned_count<>preview_count
       OR planned_records+context_records<>(
            SELECT record_count FROM plm.ai_execution_content_plans
             WHERE content_plan_id=target_plan
       )
       OR planned_count<>(
            SELECT count(*) FROM plm.ai_egress_preview_source_refs s
            JOIN plm.ai_execution_content_plans p
              ON p.egress_preview_id=s.egress_preview_id
            WHERE p.content_plan_id=target_plan
       )
    THEN
        RAISE EXCEPTION 'AI Content Plan sources are incomplete';
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_ai_content_plan_completeness
AFTER INSERT ON plm.ai_execution_content_plans
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.assert_ai_content_plan_complete();
CREATE CONSTRAINT TRIGGER trg_ai_content_source_completeness
AFTER INSERT ON plm.ai_execution_content_sources
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION plm.assert_ai_content_plan_complete();

CREATE FUNCTION plm.guard_ai_content_plan_ref_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW)->'content_plan_ref')
       IS DISTINCT FROM (to_jsonb(OLD)->'content_plan_ref') THEN
        RAISE EXCEPTION 'AI Content Plan reference is immutable';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_egress_authorizations__content_plan_ref_immutable
BEFORE UPDATE ON plm.ai_egress_authorizations
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_content_plan_ref_immutable();
CREATE TRIGGER trg_ai_tasks__content_plan_ref_immutable
BEFORE UPDATE ON plm.ai_tasks
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_content_plan_ref_immutable();
CREATE TRIGGER trg_ai_egress_authorization_snapshots__content_plan_ref_immutable
BEFORE UPDATE ON plm.ai_egress_authorization_snapshots
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_content_plan_ref_immutable();
CREATE TRIGGER trg_ai_invocations__content_plan_ref_immutable
BEFORE UPDATE ON plm.ai_invocations
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_content_plan_ref_immutable();
"""
