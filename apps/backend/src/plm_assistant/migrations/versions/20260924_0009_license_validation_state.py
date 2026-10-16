"""LIC-02 validation singleton and append-only verification events."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0009"
down_revision = "20260924_0008"
branch_labels = None
depends_on = None

CODES = "'VALID','NOT_INSTALLED','MALFORMED','SIGNATURE_INVALID','MACHINE_MISMATCH','NOT_YET_VALID','EXPIRED','TIME_ROLLBACK','PRODUCT_MISMATCH','TRUST_STATE_INVALID'"


def upgrade() -> None:
    if not context.is_offline_mode() and op.get_bind().scalar(sa.text("SELECT count(*) FROM plm.lic_installations WHERE validation_result_ref IS NOT NULL")):
        raise RuntimeError("preexisting license validation refs need controlled reconciliation before upgrade")
    op.create_table(
        "lic_validation_events",
        sa.Column("validation_event_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("validation_code", sa.Text(), nullable=False),
        sa.Column("machine_fingerprint_hash", sa.LargeBinary()),
        sa.Column("document_sha256", sa.LargeBinary()),
        sa.Column("entitlement_snapshot", postgresql.JSONB()),
        sa.Column("validated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(f"validation_code IN ({CODES})", name="ck_lic_validation_events__code"),
        sa.CheckConstraint("machine_fingerprint_hash IS NULL OR octet_length(machine_fingerprint_hash) = 32", name="ck_lic_validation_events__fingerprint"),
        sa.CheckConstraint("document_sha256 IS NULL OR octet_length(document_sha256) = 32", name="ck_lic_validation_events__document_sha256"),
        sa.CheckConstraint("entitlement_snapshot IS NULL OR jsonb_typeof(entitlement_snapshot) = 'object'", name="ck_lic_validation_events__entitlement"),
        schema="plm",
    )
    op.create_index("ix_lic_validation_events__installation_time", "lic_validation_events", ["installation_id", "validated_at"], schema="plm")
    op.create_foreign_key("fk_lic_installations__validation_result", "lic_installations", "lic_validation_events", ["validation_result_ref"], ["validation_event_id"], source_schema="plm", referent_schema="plm", ondelete="NO ACTION")
    op.create_index("ix_lic_installations__validation_result_ref", "lic_installations", ["validation_result_ref"], schema="plm")
    op.create_table(
        "lic_validation_states",
        sa.Column("license_validation_state_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("singleton_key", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("active_license_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("machine_fingerprint_hash", sa.LargeBinary()),
        sa.Column("validation_code", sa.Text(), nullable=False, server_default=sa.text("'NOT_INSTALLED'")),
        sa.Column("entitlement_snapshot", postgresql.JSONB()),
        sa.Column("validated_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("current_event_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["active_license_ref"], ["plm.lic_installations.license_installation_id"], name="fk_lic_validation_states__active_installation", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["current_event_ref"], ["plm.lic_validation_events.validation_event_id"], name="fk_lic_validation_states__event", ondelete="NO ACTION"),
        sa.UniqueConstraint("singleton_key", name="uq_lic_validation_states__singleton"),
        sa.CheckConstraint("singleton_key = 1", name="ck_lic_validation_states__singleton"),
        sa.CheckConstraint(f"validation_code IN ({CODES})", name="ck_lic_validation_states__code"),
        sa.CheckConstraint("machine_fingerprint_hash IS NULL OR octet_length(machine_fingerprint_hash) = 32", name="ck_lic_validation_states__fingerprint"),
        sa.CheckConstraint("entitlement_snapshot IS NULL OR jsonb_typeof(entitlement_snapshot) = 'object'", name="ck_lic_validation_states__entitlement"),
        sa.CheckConstraint("state_version >= 0", name="ck_lic_validation_states__version"),
        sa.CheckConstraint("validated_at IS NULL OR validated_at <= updated_at", name="ck_lic_validation_states__time"),
        sa.CheckConstraint("validation_code <> 'VALID' OR (active_license_ref IS NOT NULL AND machine_fingerprint_hash IS NOT NULL AND current_event_ref IS NOT NULL AND entitlement_snapshot IS NOT NULL AND validated_at IS NOT NULL)", name="ck_lic_validation_states__valid_shape"),
        sa.CheckConstraint("validation_code <> 'NOT_INSTALLED' OR active_license_ref IS NULL", name="ck_lic_validation_states__not_installed"),
        schema="plm",
    )
    op.create_index("ix_lic_validation_states__active_license_ref", "lic_validation_states", ["active_license_ref"], schema="plm")
    op.create_index("ix_lic_validation_states__current_event_ref", "lic_validation_states", ["current_event_ref"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_lic_validation_event_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'license validation event is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_validation_events_guard
        BEFORE UPDATE OR DELETE ON plm.lic_validation_events
        FOR EACH ROW EXECUTE FUNCTION plm.guard_lic_validation_event_change()
    """)
    op.execute("""
        CREATE FUNCTION plm.guard_lic_validation_state_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'license validation state cannot be deleted';
            END IF;
            IF NEW.singleton_key IS DISTINCT FROM OLD.singleton_key
               OR NEW.state_version <> OLD.state_version + 1
               OR NEW.updated_at < OLD.updated_at
               OR NEW.current_event_ref IS NOT DISTINCT FROM OLD.current_event_ref
            THEN
                RAISE EXCEPTION 'invalid license validation state transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_validation_states_guard
        BEFORE UPDATE OR DELETE ON plm.lic_validation_states
        FOR EACH ROW EXECUTE FUNCTION plm.guard_lic_validation_state_change()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: validation history must be checked")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM plm.lic_validation_states")) or bind.scalar(sa.text("SELECT count(*) FROM plm.lic_validation_events")):
        raise RuntimeError("license validation history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_lic_validation_states_guard ON plm.lic_validation_states")
    op.execute("DROP FUNCTION plm.guard_lic_validation_state_change()")
    op.execute("DROP TRIGGER trg_lic_validation_events_guard ON plm.lic_validation_events")
    op.execute("DROP FUNCTION plm.guard_lic_validation_event_change()")
    op.drop_index("ix_lic_validation_states__current_event_ref", table_name="lic_validation_states", schema="plm")
    op.drop_index("ix_lic_validation_states__active_license_ref", table_name="lic_validation_states", schema="plm")
    op.drop_table("lic_validation_states", schema="plm")
    op.drop_index("ix_lic_installations__validation_result_ref", table_name="lic_installations", schema="plm")
    op.drop_constraint("fk_lic_installations__validation_result", "lic_installations", schema="plm", type_="foreignkey")
    op.drop_index("ix_lic_validation_events__installation_time", table_name="lic_validation_events", schema="plm")
    op.drop_table("lic_validation_events", schema="plm")
