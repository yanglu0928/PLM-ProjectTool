"""CR-AI-005: immutable first AIModel safe state result.

Revision ID: 20261002_0058
Revises: 20261002_0057
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0058"
down_revision = "20261002_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "ai_model_state_results",
        sa.Column("state_result_id", ident, primary_key=True),
        sa.Column("ai_model_id", ident, nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("before_state", sa.Text(), nullable=False),
        sa.Column("result_state", sa.Text(), nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("accepted_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["ai_model_id"], ["plm.ai_models.ai_model_id"],
                                name="fk_ai_model_state_results__model", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_ai_model_state_results__actor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["audit_event_id"], ["plm.aud_events.audit_event_id"],
                                name="fk_ai_model_state_results__audit", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_model_id", "lock_version",
                            name="uq_ai_model_state_results__model_version"),
        sa.UniqueConstraint("audit_event_id", name="uq_ai_model_state_results__audit"),
        sa.CheckConstraint(
            "state_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_model_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ((operation = 'SUSPEND' AND before_state = 'AVAILABLE' AND result_state = 'SUSPENDED') "
            "OR (operation = 'RETIRE' AND before_state IN ('AVAILABLE','SUSPENDED') "
            "AND result_state = 'RETIRED')) "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_model_state_results__shape",
        ),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_ai_model_state_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AIModel state result history is immutable';
        END; $$;
        CREATE TRIGGER trg_ai_model_state_result_guard
        BEFORE UPDATE OR DELETE ON plm.ai_model_state_results
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_model_state_result();
        CREATE TRIGGER trg_ai_model_state_result_truncate_guard
        BEFORE TRUNCATE ON plm.ai_model_state_results
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_model_state_result();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AIModel state result downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_model_state_results IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_model_state_results) THEN
                RAISE EXCEPTION 'AIModel state result history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_model_state_result_truncate_guard ON plm.ai_model_state_results")
    op.execute("DROP TRIGGER trg_ai_model_state_result_guard ON plm.ai_model_state_results")
    op.execute("DROP FUNCTION plm.guard_ai_model_state_result()")
    op.drop_table("ai_model_state_results", schema="plm")
