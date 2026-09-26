"""LIC-03 deployment trusted-time singleton and append-only check events."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0010"
down_revision = "20260924_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lic_trusted_time_events",
        sa.Column("trusted_time_event_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("event_code", sa.Text(), nullable=False),
        sa.Column("observed_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("candidate_time", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("length(btrim(event_code)) BETWEEN 1 AND 64", name="ck_lic_trusted_time_events__code"),
        sa.CheckConstraint("details IS NULL OR jsonb_typeof(details) = 'object'", name="ck_lic_trusted_time_events__details"),
        schema="plm",
    )
    op.create_table(
        "lic_trusted_time_states",
        sa.Column("trusted_time_state_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("singleton_key", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_successful_time", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("integrity_metadata", postgresql.JSONB()),
        sa.Column("last_success_event_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["last_success_event_ref"], ["plm.lic_trusted_time_events.trusted_time_event_id"], name="fk_lic_trusted_time_states__event", ondelete="NO ACTION"),
        sa.UniqueConstraint("singleton_key", name="uq_lic_trusted_time_states__singleton"),
        sa.CheckConstraint("singleton_key = 1", name="ck_lic_trusted_time_states__singleton"),
        sa.CheckConstraint("state_version >= 0", name="ck_lic_trusted_time_states__version"),
        sa.CheckConstraint("integrity_metadata IS NULL OR jsonb_typeof(integrity_metadata) = 'object'", name="ck_lic_trusted_time_states__integrity"),
        sa.CheckConstraint("(last_successful_time IS NULL AND state_version = 0 AND integrity_metadata IS NULL AND last_success_event_ref IS NULL) OR (last_successful_time IS NOT NULL AND state_version > 0 AND integrity_metadata IS NOT NULL AND last_success_event_ref IS NOT NULL)", name="ck_lic_trusted_time_states__shape"),
        sa.CheckConstraint("last_successful_time IS NULL OR updated_at >= last_successful_time", name="ck_lic_trusted_time_states__time"),
        schema="plm",
    )
    op.create_index("ix_lic_trusted_time_states__last_success_event_ref", "lic_trusted_time_states", ["last_success_event_ref"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_lic_trusted_time_event_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'trusted-time event is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_trusted_time_events_guard
        BEFORE UPDATE OR DELETE ON plm.lic_trusted_time_events
        FOR EACH ROW EXECUTE FUNCTION plm.guard_lic_trusted_time_event_change()
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_trusted_time_events_truncate_guard
        BEFORE TRUNCATE ON plm.lic_trusted_time_events
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_lic_trusted_time_event_change()
    """)
    op.execute("""
        CREATE FUNCTION plm.guard_lic_trusted_time_state_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
                RAISE EXCEPTION 'trusted-time state cannot be deleted';
            END IF;
            IF NEW.trusted_time_state_id IS DISTINCT FROM OLD.trusted_time_state_id
               OR NEW.singleton_key IS DISTINCT FROM OLD.singleton_key
               OR NEW.state_version <> OLD.state_version + 1
               OR NEW.last_successful_time IS NULL
               OR (OLD.last_successful_time IS NOT NULL AND NEW.last_successful_time <= OLD.last_successful_time)
               OR NEW.updated_at < OLD.updated_at
               OR NEW.last_success_event_ref IS NOT DISTINCT FROM OLD.last_success_event_ref
            THEN
                RAISE EXCEPTION 'invalid trusted-time state transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_trusted_time_states_guard
        BEFORE UPDATE OR DELETE ON plm.lic_trusted_time_states
        FOR EACH ROW EXECUTE FUNCTION plm.guard_lic_trusted_time_state_change()
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_trusted_time_states_truncate_guard
        BEFORE TRUNCATE ON plm.lic_trusted_time_states
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_lic_trusted_time_state_change()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: trusted-time history must be checked")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM plm.lic_trusted_time_states")) or bind.scalar(sa.text("SELECT count(*) FROM plm.lic_trusted_time_events")):
        raise RuntimeError("trusted-time history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_lic_trusted_time_states_truncate_guard ON plm.lic_trusted_time_states")
    op.execute("DROP TRIGGER trg_lic_trusted_time_states_guard ON plm.lic_trusted_time_states")
    op.execute("DROP FUNCTION plm.guard_lic_trusted_time_state_change()")
    op.execute("DROP TRIGGER trg_lic_trusted_time_events_truncate_guard ON plm.lic_trusted_time_events")
    op.execute("DROP TRIGGER trg_lic_trusted_time_events_guard ON plm.lic_trusted_time_events")
    op.execute("DROP FUNCTION plm.guard_lic_trusted_time_event_change()")
    op.drop_index("ix_lic_trusted_time_states__last_success_event_ref", table_name="lic_trusted_time_states", schema="plm")
    op.drop_table("lic_trusted_time_states", schema="plm")
    op.drop_table("lic_trusted_time_events", schema="plm")
