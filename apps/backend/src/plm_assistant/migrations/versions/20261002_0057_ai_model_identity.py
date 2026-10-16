"""AI-02 immutable model semantics and capability/quality references.

Revision ID: 20261002_0057
Revises: 20261002_0056
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0057"
down_revision = "20261002_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_models",
        sa.Column("ai_model_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_model_key", sa.Text(), nullable=False),
        sa.Column("model_kind", sa.Text(), nullable=False),
        sa.Column("model_revision", sa.Text(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer()),
        sa.Column("model_state", sa.Text(), nullable=False, server_default=sa.text("'SUSPENDED'")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["ai_provider_id"], ["plm.ai_providers.ai_provider_id"],
                                name="fk_ai_models__ai_provider_id__ai_providers", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_ai_models__created_by__auth_users", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_provider_id", "provider_model_key", "model_kind", "model_revision", "embedding_dimension",
                            name="uq_ai_models__semantic_identity", postgresql_nulls_not_distinct=True),
        sa.CheckConstraint(
            "ai_model_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_models__ids"),
        sa.CheckConstraint("provider_model_key ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'", name="ck_ai_models__key"),
        sa.CheckConstraint("model_revision = 'PROVIDER_MANAGED' OR model_revision ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'",
                           name="ck_ai_models__revision"),
        sa.CheckConstraint("model_kind IN ('CHAT','EMBEDDING','RERANK')", name="ck_ai_models__kind"),
        sa.CheckConstraint("(model_kind = 'EMBEDDING' AND embedding_dimension IS NOT NULL "
                           "AND embedding_dimension BETWEEN 1 AND 65536) "
                           "OR (model_kind <> 'EMBEDDING' AND embedding_dimension IS NULL)", name="ck_ai_models__dimension"),
        sa.CheckConstraint("model_state IN ('AVAILABLE','SUSPENDED','RETIRED') AND lock_version >= 0",
                           name="ck_ai_models__state"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_ai_models__time"),
        schema="plm",
    )
    op.create_index("ix_ai_models__provider_state", "ai_models",
                    ["ai_provider_id", "model_state", "ai_model_id"], schema="plm")
    op.create_table(
        "ai_model_capabilities",
        sa.Column("ai_model_id", ident, primary_key=True),
        sa.Column("capability_code", sa.Text(), primary_key=True),
        sa.Column("value_bool", sa.Boolean()),
        sa.Column("value_integer", sa.Integer()),
        sa.ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"],
                                name="fk_ai_model_capabilities__ai_model_id__ai_models", ondelete="NO ACTION"),
        sa.CheckConstraint("capability_code IN ('STRUCTURED_OUTPUT','CONTEXT_WINDOW_TOKENS')",
                           name="ck_ai_model_capabilities__code"),
        sa.CheckConstraint("(capability_code = 'STRUCTURED_OUTPUT' AND value_bool IS NOT NULL AND value_integer IS NULL) "
                           "OR (capability_code = 'CONTEXT_WINDOW_TOKENS' AND value_bool IS NULL "
                           "AND value_integer IS NOT NULL AND value_integer BETWEEN 1 AND 1048576)",
                           name="ck_ai_model_capabilities__value"),
        schema="plm",
    )
    op.create_table(
        "ai_quality_profile_refs",
        sa.Column("ai_model_id", ident, primary_key=True),
        sa.Column("quality_profile_ref", sa.Text(), primary_key=True),
        sa.Column("linked_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"],
                                name="fk_ai_quality_profile_refs__ai_model_id__ai_models", ondelete="NO ACTION"),
        sa.CheckConstraint("quality_profile_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
                           name="ck_ai_quality_profile_refs__ref"),
        sa.CheckConstraint("isfinite(linked_at)", name="ck_ai_quality_profile_refs__time"),
        schema="plm",
    )
    op.create_index("ix_ai_quality_profile_refs__profile", "ai_quality_profile_refs",
                    ["quality_profile_ref"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_ai_model_semantics() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE' OR TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'AIModel identity history is immutable';
            END IF;
            IF ROW(NEW.ai_model_id, NEW.ai_provider_id, NEW.provider_model_key,
                   NEW.model_kind, NEW.model_revision, NEW.embedding_dimension,
                   NEW.created_by, NEW.created_at) IS DISTINCT FROM
               ROW(OLD.ai_model_id, OLD.ai_provider_id, OLD.provider_model_key,
                   OLD.model_kind, OLD.model_revision, OLD.embedding_dimension,
                   OLD.created_by, OLD.created_at) THEN
                RAISE EXCEPTION 'AIModel semantics are immutable';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER trg_ai_models_semantics_guard BEFORE UPDATE OR DELETE ON plm.ai_models
            FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_model_semantics();
        CREATE TRIGGER trg_ai_models_truncate_guard BEFORE TRUNCATE ON plm.ai_models
            FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_model_semantics();
        CREATE FUNCTION plm.guard_ai_model_child_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AIModel capability and quality history is immutable';
        END; $$;
        CREATE TRIGGER trg_ai_model_capabilities_guard BEFORE UPDATE OR DELETE ON plm.ai_model_capabilities
            FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_model_child_history();
        CREATE TRIGGER trg_ai_model_capabilities_truncate_guard BEFORE TRUNCATE ON plm.ai_model_capabilities
            FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_model_child_history();
        CREATE TRIGGER trg_ai_quality_profile_refs_guard BEFORE UPDATE OR DELETE ON plm.ai_quality_profile_refs
            FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_model_child_history();
        CREATE TRIGGER trg_ai_quality_profile_refs_truncate_guard BEFORE TRUNCATE ON plm.ai_quality_profile_refs
            FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_model_child_history();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AIModel downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_models, plm.ai_model_capabilities, plm.ai_quality_profile_refs IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_models)
               OR EXISTS (SELECT 1 FROM plm.ai_model_capabilities)
               OR EXISTS (SELECT 1 FROM plm.ai_quality_profile_refs) THEN
                RAISE EXCEPTION 'AIModel history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_quality_profile_refs_truncate_guard ON plm.ai_quality_profile_refs")
    op.execute("DROP TRIGGER trg_ai_quality_profile_refs_guard ON plm.ai_quality_profile_refs")
    op.execute("DROP TRIGGER trg_ai_model_capabilities_truncate_guard ON plm.ai_model_capabilities")
    op.execute("DROP TRIGGER trg_ai_model_capabilities_guard ON plm.ai_model_capabilities")
    op.execute("DROP FUNCTION plm.guard_ai_model_child_history()")
    op.execute("DROP TRIGGER trg_ai_models_truncate_guard ON plm.ai_models")
    op.execute("DROP TRIGGER trg_ai_models_semantics_guard ON plm.ai_models")
    op.execute("DROP FUNCTION plm.guard_ai_model_semantics()")
    op.drop_index("ix_ai_quality_profile_refs__profile", table_name="ai_quality_profile_refs", schema="plm")
    op.drop_table("ai_quality_profile_refs", schema="plm")
    op.drop_table("ai_model_capabilities", schema="plm")
    op.drop_index("ix_ai_models__provider_state", table_name="ai_models", schema="plm")
    op.drop_table("ai_models", schema="plm")
