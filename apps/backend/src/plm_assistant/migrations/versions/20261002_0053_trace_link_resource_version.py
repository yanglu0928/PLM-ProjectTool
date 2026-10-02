"""CR-TRC-003: database-owned TraceLink state resource version.

Revision ID: 20261002_0053
Revises: 20261001_0052
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op


revision = "20261002_0053"
down_revision = "20261001_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trc_links",
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        schema="plm",
    )
    # Alembic runs PostgreSQL DDL in one transaction.  Keep the original
    # history guard disabled only while this table is exclusively locked.
    op.execute("LOCK TABLE plm.trc_links IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE plm.trc_links DISABLE TRIGGER trg_trc_link_guard")
    op.execute("UPDATE plm.trc_links SET lock_version=1 WHERE link_state<>'ACTIVE'")
    op.execute("ALTER TABLE plm.trc_links ENABLE TRIGGER trg_trc_link_guard")
    op.create_check_constraint(
        "ck_trc_links__resource_version", "trc_links",
        "(link_state='ACTIVE' AND lock_version=0) OR "
        "(link_state IN ('SUPERSEDED','REVOKED') AND lock_version=1)",
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_trace_link_resource_version()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.lock_version<>0 THEN
                    RAISE EXCEPTION 'TraceLink initial resource version invalid';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.lock_version IS DISTINCT FROM OLD.lock_version THEN
                RAISE EXCEPTION 'TraceLink resource version is database-owned';
            END IF;
            IF OLD.link_state='ACTIVE' AND NEW.link_state IN ('REVOKED','SUPERSEDED') THEN
                IF OLD.lock_version<>0 THEN
                    RAISE EXCEPTION 'TraceLink active resource version invalid';
                END IF;
                NEW.lock_version := 1;
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_trc_link_resource_version
        BEFORE INSERT OR UPDATE ON plm.trc_links
        FOR EACH ROW EXECUTE FUNCTION plm.guard_trace_link_resource_version();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline TraceLink version downgrade is disabled")
    op.execute("LOCK TABLE plm.trc_links IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM plm.trc_links
                WHERE link_state<>'ACTIVE' OR lock_version<>0
            ) THEN
                RAISE EXCEPTION 'TraceLink terminal version history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_trc_link_resource_version ON plm.trc_links")
    op.execute("DROP FUNCTION plm.guard_trace_link_resource_version()")
    op.drop_constraint("ck_trc_links__resource_version", "trc_links",
                       schema="plm", type_="check")
    op.drop_column("trc_links", "lock_version", schema="plm")
