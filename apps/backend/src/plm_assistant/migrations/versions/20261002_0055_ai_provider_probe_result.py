"""CR-AI-002: immutable Provider probe result bound to config, Secret and Job.

Revision ID: 20261002_0055
Revises: 20261002_0054
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261002_0055"
down_revision = "20261002_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_unique_constraint(
        "uq_ai_provider_configs__identity_secret", "ai_provider_config_versions",
        ["provider_config_version_id", "ai_provider_id", "secret_ref"], schema="plm",
    )
    op.create_table(
        "ai_provider_probe_results",
        sa.Column("probe_result_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_config_version_id", ident, nullable=False),
        sa.Column("secret_record_id", ident, nullable=False),
        sa.Column("secret_version_id", ident, nullable=False),
        sa.Column("job_id", ident, nullable=False),
        sa.Column("probe_id", sa.Text(), nullable=False),
        sa.Column("policy_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("failure_code", sa.Text()),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("observed_at", timestamp, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False, server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id", "secret_record_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id",
             "plm.ai_provider_config_versions.secret_ref"],
            name="fk_ai_provider_probe_results__config_secret", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["secret_version_id", "secret_record_id"],
            ["plm.plt_secret_versions.secret_version_id", "plm.plt_secret_versions.secret_record_id"],
            name="fk_ai_provider_probe_results__secret_version", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "attempt_no"], ["plm.job_attempts.job_id", "plm.job_attempts.attempt_no"],
            name="fk_ai_provider_probe_results__attempt", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "fencing_token"], ["plm.job_leases.job_id", "plm.job_leases.fencing_token"],
            name="fk_ai_provider_probe_results__lease", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"],
                                name="fk_ai_provider_probe_results__job_id__job_jobs", ondelete="NO ACTION"),
        sa.UniqueConstraint("job_id", name="uq_ai_provider_probe_results__job"),
        sa.CheckConstraint(
            "probe_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND secret_record_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND secret_version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND job_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_provider_probe_results__ids",
        ),
        sa.CheckConstraint("probe_id = 'CHAT_CONNECTIVITY_V1'", name="ck_ai_provider_probe_results__probe"),
        sa.CheckConstraint("octet_length(policy_sha256) = 32", name="ck_ai_provider_probe_results__policy_digest"),
        sa.CheckConstraint("attempt_no > 0 AND fencing_token > 0 AND created_xid > 0", name="ck_ai_provider_probe_results__attempt"),
        sa.CheckConstraint(
            "(outcome = 'SUCCEEDED' AND failure_code IS NULL) OR "
            "(outcome = 'FAILED' AND failure_code IS NOT NULL "
            "AND failure_code ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_ai_provider_probe_results__outcome",
        ),
        sa.CheckConstraint("isfinite(observed_at) AND isfinite(created_at)", name="ck_ai_provider_probe_results__time"),
        schema="plm",
    )
    op.create_index("ix_ai_provider_probe_results__provider_time", "ai_provider_probe_results",
                    ["ai_provider_id", "observed_at", "probe_result_id"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_ai_provider_probe_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'AIProvider probe result history is immutable';
        END;
        $$;
        CREATE TRIGGER trg_ai_provider_probe_result_guard
        BEFORE UPDATE OR DELETE ON plm.ai_provider_probe_results
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_provider_probe_result();
        CREATE TRIGGER trg_ai_provider_probe_result_truncate_guard
        BEFORE TRUNCATE ON plm.ai_provider_probe_results
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_provider_probe_result();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AIProvider probe result downgrade is disabled")
    op.execute("LOCK TABLE plm.ai_provider_probe_results IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.ai_provider_probe_results) THEN
                RAISE EXCEPTION 'AIProvider probe result history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_ai_provider_probe_result_truncate_guard ON plm.ai_provider_probe_results")
    op.execute("DROP TRIGGER trg_ai_provider_probe_result_guard ON plm.ai_provider_probe_results")
    op.execute("DROP FUNCTION plm.guard_ai_provider_probe_result()")
    op.drop_index("ix_ai_provider_probe_results__provider_time", table_name="ai_provider_probe_results", schema="plm")
    op.drop_table("ai_provider_probe_results", schema="plm")
    op.drop_constraint("uq_ai_provider_configs__identity_secret", "ai_provider_config_versions", schema="plm", type_="unique")
