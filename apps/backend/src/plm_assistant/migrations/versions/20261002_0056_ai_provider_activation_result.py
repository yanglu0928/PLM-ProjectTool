"""CR-AI-002: immutable first Provider ACTIVE result for safe replay.

Revision ID: 20261002_0056
Revises: 20261002_0055
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0056"
down_revision = "20261002_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_unique_constraint(
        "uq_ai_provider_probe_results__identity_config", "ai_provider_probe_results",
        ["probe_result_id", "ai_provider_id", "provider_config_version_id"], schema="plm",
    )
    op.create_table(
        "ai_provider_activation_results",
        sa.Column("activation_result_id", ident, primary_key=True),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_config_version_id", ident, nullable=False),
        sa.Column("probe_result_id", ident, nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("before_state", sa.Text(), nullable=False),
        sa.Column("result_state", sa.Text(), nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("accepted_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(["ai_provider_id"], ["plm.ai_providers.ai_provider_id"],
                                name="fk_ai_provider_activation_results__provider", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_provider_activation_results__config_provider", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["probe_result_id", "ai_provider_id", "provider_config_version_id"],
            ["plm.ai_provider_probe_results.probe_result_id",
             "plm.ai_provider_probe_results.ai_provider_id",
             "plm.ai_provider_probe_results.provider_config_version_id"],
            name="fk_ai_provider_activation_results__probe_config", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_ai_provider_activation_results__actor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["audit_event_id"], ["plm.aud_events.audit_event_id"],
                                name="fk_ai_provider_activation_results__audit", ondelete="NO ACTION"),
        sa.UniqueConstraint("ai_provider_id", "lock_version",
                            name="uq_ai_provider_activation_results__provider_version"),
        sa.UniqueConstraint("audit_event_id", name="uq_ai_provider_activation_results__audit"),
        sa.CheckConstraint(
            "activation_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND probe_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND before_state IN ('CONFIGURED','SUSPENDED') AND result_state = 'ACTIVE' "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_provider_activation_results__shape",
        ),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_ai_provider_activation_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AIProvider activation result history is immutable';
        END;
        $$;
        CREATE TRIGGER trg_ai_provider_activation_result_guard
        BEFORE UPDATE OR DELETE ON plm.ai_provider_activation_results
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_provider_activation_result();
        CREATE TRIGGER trg_ai_provider_activation_result_truncate_guard
        BEFORE TRUNCATE ON plm.ai_provider_activation_results
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_provider_activation_result();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AIProvider activation result downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_provider_activation_results IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_provider_activation_results) THEN
                RAISE EXCEPTION 'AIProvider activation result history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_provider_activation_result_truncate_guard ON plm.ai_provider_activation_results")
    op.execute("DROP TRIGGER trg_ai_provider_activation_result_guard ON plm.ai_provider_activation_results")
    op.execute("DROP FUNCTION plm.guard_ai_provider_activation_result()")
    op.drop_table("ai_provider_activation_results", schema="plm")
    op.drop_constraint("uq_ai_provider_probe_results__identity_config",
                       "ai_provider_probe_results", schema="plm", type_="unique")
