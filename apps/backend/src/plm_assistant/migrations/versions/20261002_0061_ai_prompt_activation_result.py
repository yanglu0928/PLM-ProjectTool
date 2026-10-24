"""CR-AI-008 immutable first PromptVersion activation result.

Revision ID: 20261002_0061
Revises: 20261002_0060
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0061"
down_revision = "20261002_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_prompt_activation_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("prompt_template_id", ident, nullable=False),
        sa.Column("version_no", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("accepted_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["prompt_template_id", "version_no"],
            ["plm.ai_prompt_versions.prompt_template_id", "plm.ai_prompt_versions.version_no"],
            name="fk_ai_prompt_activation_results__version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_ai_prompt_activation_results__actor_id__auth_users",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["audit_event_id"], ["plm.aud_events.audit_event_id"],
                                name="fk_ai_prompt_activation_results__audit_event_id__aud_events",
                                ondelete="NO ACTION"),
        sa.UniqueConstraint("audit_event_id", name="uq_ai_prompt_activation_results__audit"),
        sa.CheckConstraint(
            "result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND prompt_template_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_no > 0 AND state = 'ACTIVE' "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_prompt_activation_results__shape",
        ),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_ai_prompt_activation_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Prompt activation result history is immutable';
        END; $$;
        CREATE TRIGGER trg_ai_prompt_activation_result_guard
        BEFORE UPDATE OR DELETE ON plm.ai_prompt_activation_results
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_prompt_activation_result();
        CREATE TRIGGER trg_ai_prompt_activation_result_truncate_guard
        BEFORE TRUNCATE ON plm.ai_prompt_activation_results
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_prompt_activation_result();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prompt activation result downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_prompt_activation_results IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_prompt_activation_results) THEN
                RAISE EXCEPTION 'Prompt activation result history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_prompt_activation_result_truncate_guard "
               "ON plm.ai_prompt_activation_results")
    op.execute("DROP TRIGGER trg_ai_prompt_activation_result_guard "
               "ON plm.ai_prompt_activation_results")
    op.execute("DROP FUNCTION plm.guard_ai_prompt_activation_result()")
    op.drop_table("ai_prompt_activation_results", schema="plm")
