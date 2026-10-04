"""CR-AI-001: deployment AIProvider identity and immutable config versions.

Revision ID: 20261002_0054
Revises: 20261002_0053
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0054"
down_revision = "20261002_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_providers",
        sa.Column("ai_provider_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("current_config_version_ref", ident, nullable=False),
        sa.Column("provider_state", sa.Text(), nullable=False, server_default=sa.text("'CONFIGURED'")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_ai_providers__created_by__auth_users", ondelete="NO ACTION"),
        sa.CheckConstraint("provider_state IN ('CONFIGURED','ACTIVE','SUSPENDED','RETIRED') AND lock_version >= 0", name="ck_ai_providers__state"),
        sa.CheckConstraint("ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid AND current_config_version_ref <> '00000000-0000-0000-0000-000000000000'::uuid", name="ck_ai_providers__ids"),
        schema="plm",
    )
    op.create_table(
        "ai_provider_config_versions",
        sa.Column("provider_config_version_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("config_version_no", sa.Integer(), nullable=False),
        sa.Column("provider_kind", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("endpoint_policy_ref", sa.Text(), nullable=False),
        sa.Column("secret_ref", ident, nullable=False),
        sa.Column("data_region", sa.Text(), nullable=False),
        sa.Column("egress_class", sa.Text(), nullable=False),
        sa.Column("can_chat", sa.Boolean(), nullable=False),
        sa.Column("can_structured_output", sa.Boolean(), nullable=False),
        sa.Column("can_embedding", sa.Boolean(), nullable=False),
        sa.Column("can_rerank", sa.Boolean(), nullable=False),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False, server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["ai_provider_id"], ["plm.ai_providers.ai_provider_id"], name="fk_ai_provider_config_versions__ai_provider_id__ai_providers", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["secret_ref"], ["plm.plt_secret_records.secret_record_id"], name="fk_ai_provider_config_versions__secret_ref__plt_secret_records", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_ai_provider_config_versions__created_by__auth_users", ondelete="NO ACTION"),
        sa.UniqueConstraint("provider_config_version_id", "ai_provider_id", name="uq_ai_provider_configs__id_provider"),
        sa.UniqueConstraint("ai_provider_id", "config_version_no", name="uq_ai_provider_configs__provider_no"),
        sa.CheckConstraint("provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid AND secret_ref <> '00000000-0000-0000-0000-000000000000'::uuid", name="ck_ai_provider_configs__ids"),
        sa.CheckConstraint("config_version_no > 0 AND created_xid > 0", name="ck_ai_provider_configs__version"),
        sa.CheckConstraint("provider_kind IN ('OPENAI_COMPATIBLE','ANTHROPIC_MESSAGES','GEMINI_NATIVE','CUSTOM')", name="ck_ai_provider_configs__kind"),
        sa.CheckConstraint("char_length(display_name) BETWEEN 1 AND 120 AND char_length(btrim(display_name)) > 0", name="ck_ai_provider_configs__display_name"),
        sa.CheckConstraint("char_length(endpoint_policy_ref) BETWEEN 1 AND 128 AND endpoint_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:-]*$'", name="ck_ai_provider_configs__endpoint_ref"),
        sa.CheckConstraint("char_length(data_region) BETWEEN 1 AND 64 AND data_region ~ '^[a-z][a-z0-9-]*$'", name="ck_ai_provider_configs__region"),
        sa.CheckConstraint("char_length(egress_class) BETWEEN 1 AND 64 AND egress_class ~ '^[A-Z][A-Z0-9_]*$'", name="ck_ai_provider_configs__egress"),
        sa.CheckConstraint("can_chat OR can_structured_output OR can_embedding OR can_rerank", name="ck_ai_provider_configs__capabilities"),
        schema="plm",
    )
    op.create_index("ix_ai_provider_configs__secret", "ai_provider_config_versions", ["secret_ref"], schema="plm")
    op.create_index("ix_ai_provider_configs__creator", "ai_provider_config_versions", ["created_by"], schema="plm")
    op.create_foreign_key(
        "fk_ai_providers__current_config", "ai_providers", "ai_provider_config_versions",
        ["current_config_version_ref", "ai_provider_id"], ["provider_config_version_id", "ai_provider_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )
    op.create_index("ix_ai_providers__current_config", "ai_providers", ["current_config_version_ref", "ai_provider_id"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_ai_provider_config_version()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AIProvider config history is immutable';
        END;
        $$;
        CREATE TRIGGER trg_ai_provider_config_guard
        BEFORE UPDATE OR DELETE ON plm.ai_provider_config_versions
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_provider_config_version();
        CREATE TRIGGER trg_ai_provider_config_truncate_guard
        BEFORE TRUNCATE ON plm.ai_provider_config_versions
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_provider_config_version();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AIProvider downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_providers, plm.ai_provider_config_versions IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_providers)
               OR EXISTS (SELECT 1 FROM plm.ai_provider_config_versions) THEN
                RAISE EXCEPTION 'AIProvider history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_provider_config_truncate_guard ON plm.ai_provider_config_versions")
    op.execute("DROP TRIGGER trg_ai_provider_config_guard ON plm.ai_provider_config_versions")
    op.execute("DROP FUNCTION plm.guard_ai_provider_config_version()")
    op.drop_constraint("fk_ai_providers__current_config", "ai_providers", schema="plm", type_="foreignkey")
    op.drop_index("ix_ai_providers__current_config", table_name="ai_providers", schema="plm")
    op.drop_table("ai_provider_config_versions", schema="plm")
    op.drop_table("ai_providers", schema="plm")
