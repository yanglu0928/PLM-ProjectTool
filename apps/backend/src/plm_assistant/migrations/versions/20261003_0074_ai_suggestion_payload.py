"""Add immutable AI SuggestionPayload ownership and typed Evidence refs.

Revision ID: 20261003_0074
Revises: 20261003_0073
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261003_0074"
down_revision = "20261003_0073"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE FUNCTION plm.guard_ai_suggestion_payload()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE invocation_row plm.ai_invocations%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'AI SuggestionPayload history is immutable';
    END IF;
    SELECT * INTO invocation_row FROM plm.ai_invocations
     WHERE ai_invocation_id=NEW.ai_invocation_id
       AND ai_task_id=NEW.ai_task_id FOR UPDATE;
    IF NOT FOUND OR invocation_row.invocation_state<>'RUNNING'
       OR invocation_row.suggestion_payload_ref IS NOT NULL
       OR NOT invocation_row.schema_validation_required
       OR invocation_row.schema_validation_state<>'PENDING'
       OR ROW(NEW.scope,NEW.project_id,NEW.output_schema_ref,NEW.schema_version)
          IS DISTINCT FROM
          ROW(invocation_row.scope,invocation_row.project_id,
              invocation_row.output_schema_ref,invocation_row.schema_version) THEN
        RAISE EXCEPTION 'AI SuggestionPayload Invocation ownership mismatch';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(NEW.quality_flags) AS item(value)
         WHERE jsonb_typeof(value)<>'string'
            OR value #>> '{}' !~ '^[A-Z][A-Z0-9_]{0,63}$'
    ) OR (
        SELECT count(*) FROM jsonb_array_elements_text(NEW.quality_flags)
    ) <> (
        SELECT count(DISTINCT value)
          FROM jsonb_array_elements_text(NEW.quality_flags) AS item(value)
    ) THEN
        RAISE EXCEPTION 'AI SuggestionPayload quality flags are invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_suggestion_payload_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_suggestion_payloads
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_suggestion_payload();

CREATE FUNCTION plm.guard_ai_suggestion_evidence_ref()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_row plm.ai_suggestion_payloads%ROWTYPE;
        invocation_state_value text; current_payload uuid;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'AI Suggestion Evidence history is immutable';
    END IF;
    SELECT * INTO parent_row FROM plm.ai_suggestion_payloads
     WHERE suggestion_payload_id=NEW.suggestion_payload_id FOR KEY SHARE;
    IF NOT FOUND
       OR ROW(NEW.scope,NEW.project_id)
          IS DISTINCT FROM ROW(parent_row.scope,parent_row.project_id) THEN
        RAISE EXCEPTION 'AI Suggestion Evidence scope mismatch';
    END IF;
    SELECT invocation_state,suggestion_payload_ref
      INTO invocation_state_value,current_payload
      FROM plm.ai_invocations
     WHERE ai_invocation_id=parent_row.ai_invocation_id FOR UPDATE;
    IF NOT FOUND OR invocation_state_value<>'RUNNING'
       OR current_payload IS NOT NULL THEN
        RAISE EXCEPTION 'AI Suggestion Evidence set is sealed';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_ai_suggestion_evidence_ref_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_suggestion_evidence_refs
FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_suggestion_evidence_ref();

CREATE FUNCTION plm.guard_ai_suggestion_no_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'AI Suggestion history cannot be truncated';
END; $$;

CREATE TRIGGER trg_ai_suggestion_payload_no_truncate
BEFORE TRUNCATE ON plm.ai_suggestion_payloads
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_suggestion_no_truncate();
CREATE TRIGGER trg_ai_suggestion_evidence_no_truncate
BEFORE TRUNCATE ON plm.ai_suggestion_evidence_refs
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_suggestion_no_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_suggestion_payloads",
        sa.Column("suggestion_payload_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("ai_invocation_id", ident, nullable=False),
        sa.Column("ai_task_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("output_schema_ref", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.BigInteger(), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("fact_status", sa.Text(), nullable=False,
                  server_default=sa.text("'NOT_FORMAL_FACT'")),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["ai_invocation_id", "ai_task_id"],
            ["plm.ai_invocations.ai_invocation_id", "plm.ai_invocations.ai_task_id"],
            name="fk_ai_suggestion_payloads__invocation", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_suggestion_payloads__project",
                                ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_invocation_id",
                            name="uq_ai_suggestion_payloads__invocation"),
        sa.UniqueConstraint(
            "suggestion_payload_id", "ai_invocation_id", "ai_task_id",
            name="uq_ai_suggestion_payloads__identity_invocation_task",
        ),
        sa.CheckConstraint(
            "suggestion_payload_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_invocation_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_task_id<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_suggestion_payloads__ids",
        ),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_ai_suggestion_payloads__scope",
        ),
        sa.CheckConstraint(
            "output_schema_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND schema_version BETWEEN 1 AND 9223372036854775807 "
            "AND octet_length(payload_fingerprint)=32",
            name="ck_ai_suggestion_payloads__schema_fingerprint",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload)='object' "
            "AND pg_column_size(canonical_payload)<=1048576",
            name="ck_ai_suggestion_payloads__payload",
        ),
        sa.CheckConstraint(
            "fact_status='NOT_FORMAL_FACT'",
            name="ck_ai_suggestion_payloads__fact_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(quality_flags)='array' "
            "AND jsonb_array_length(quality_flags)<=64",
            name="ck_ai_suggestion_payloads__quality_flags",
        ),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_ai_suggestion_payloads__time"),
        schema="plm",
    )
    op.create_index(
        "ix_ai_suggestion_payloads__project_time", "ai_suggestion_payloads",
        ["project_id", sa.text("created_at DESC"),
         sa.text("suggestion_payload_id DESC")], schema="plm",
    )
    op.create_table(
        "ai_suggestion_evidence_refs",
        sa.Column("suggestion_evidence_ref_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("suggestion_payload_id", ident, nullable=False),
        sa.Column("ref_ordinal", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("owner_module", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", ident, nullable=False),
        sa.Column("version_id", ident, nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["suggestion_payload_id"],
            ["plm.ai_suggestion_payloads.suggestion_payload_id"],
            name="fk_ai_suggestion_evidence_refs__payload", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_ai_suggestion_evidence_refs__project",
                                ondelete="NO ACTION"),
        sa.UniqueConstraint("suggestion_payload_id", "ref_ordinal",
                            name="uq_ai_suggestion_evidence_refs__ordinal"),
        sa.UniqueConstraint(
            "suggestion_payload_id", "owner_module", "object_type",
            "object_id", "version_id",
            name="uq_ai_suggestion_evidence_refs__identity",
        ),
        sa.CheckConstraint(
            "suggestion_evidence_ref_id<>"
            "'00000000-0000-0000-0000-000000000000'::uuid "
            "AND suggestion_payload_id<>"
            "'00000000-0000-0000-0000-000000000000'::uuid "
            "AND object_id<>'00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_id<>'00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_suggestion_evidence_refs__ids",
        ),
        sa.CheckConstraint(
            "ref_ordinal BETWEEN 1 AND 256 AND "
            "((scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL))",
            name="ck_ai_suggestion_evidence_refs__scope_ordinal",
        ),
        sa.CheckConstraint(
            "owner_module ~ '^[a-z][a-z0-9_]{0,63}$' "
            "AND object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' "
            "AND octet_length(content_fingerprint)=32",
            name="ck_ai_suggestion_evidence_refs__identity",
        ),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_ai_suggestion_evidence_refs__time"),
        schema="plm",
    )
    op.create_foreign_key(
        "fk_ai_invocations__suggestion_payload",
        "ai_invocations", "ai_suggestion_payloads",
        ["suggestion_payload_ref", "ai_invocation_id", "ai_task_id"],
        ["suggestion_payload_id", "ai_invocation_id", "ai_task_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI SuggestionPayload downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.ai_suggestion_evidence_refs, "
        "plm.ai_suggestion_payloads, plm.ai_invocations IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_suggestion_payloads)
               OR EXISTS (SELECT 1 FROM plm.ai_suggestion_evidence_refs)
               OR EXISTS (SELECT 1 FROM plm.ai_invocations
                            WHERE suggestion_payload_ref IS NOT NULL) THEN
                RAISE EXCEPTION 'AI SuggestionPayload history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_suggestion_evidence_no_truncate "
               "ON plm.ai_suggestion_evidence_refs")
    op.execute("DROP TRIGGER trg_ai_suggestion_payload_no_truncate "
               "ON plm.ai_suggestion_payloads")
    op.execute("DROP TRIGGER trg_ai_suggestion_evidence_ref_guard "
               "ON plm.ai_suggestion_evidence_refs")
    op.execute("DROP TRIGGER trg_ai_suggestion_payload_guard "
               "ON plm.ai_suggestion_payloads")
    op.execute("DROP FUNCTION plm.guard_ai_suggestion_no_truncate()")
    op.execute("DROP FUNCTION plm.guard_ai_suggestion_evidence_ref()")
    op.execute("DROP FUNCTION plm.guard_ai_suggestion_payload()")
    op.drop_constraint("fk_ai_invocations__suggestion_payload", "ai_invocations",
                       schema="plm", type_="foreignkey")
    op.drop_table("ai_suggestion_evidence_refs", schema="plm")
    op.drop_index("ix_ai_suggestion_payloads__project_time",
                  table_name="ai_suggestion_payloads", schema="plm")
    op.drop_table("ai_suggestion_payloads", schema="plm")
