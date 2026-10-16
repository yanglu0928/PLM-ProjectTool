"""AUD-01 AuditEvent: scoped, safe-metadata, append-only event store."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0005"
down_revision = "20260924_0004"
branch_labels = None
depends_on = None

# Frozen SC-02 Root whitelist; do not import mutable ORM from a historical revision.
TARGET_ROOTS = {
    "platform": ("PLT-01", "PLT-02"), "auth": ("AUT-01", "AUT-02"),
    "project": ("PRJ-01", "PRJ-02", "PRJ-03"), "workflow": ("WFL-01", "WFL-02"),
    "review": ("RVW-01", "RVW-02"), "trace": ("TRC-01",), "audit": ("AUD-01",),
    "license": ("LIC-01", "LIC-02", "LIC-03"),
    "document": ("DOC-01", "DOC-02", "DOC-03", "DOC-04"),
    "evidence": ("EVD-01", "EVD-02"), "jobs": ("JOB-01", "JOB-02"),
    "ai": ("AI-01", "AI-02", "AI-03", "AI-04"),
    "rag": ("RAG-01", "RAG-02", "RAG-03", "RAG-04"),
    "capability": ("CAP-01", "CAP-02"), "handover": ("HND-01", "HND-02", "HND-03"),
    "survey": ("SRV-01", "SRV-02", "SRV-03", "SRV-04", "SRV-05"),
    "requirement": ("REQ-01", "REQ-02", "REQ-03", "REQ-04"),
    "prototype": ("PRT-01", "PRT-02", "PRT-03", "PRT-04", "PRT-05"),
    "solution": ("SOL-01", "SOL-02", "SOL-03", "SOL-04", "SOL-05", "SOL-06"),
    "plan": ("PLN-01", "PLN-02", "PLN-03"), "output": ("OUT-01", "OUT-02"),
    "plugin": ("PLG-01", "PLG-02", "PLG-03"),
}


def _target_pair_check() -> str:
    clauses = []
    for owner, roots in TARGET_ROOTS.items():
        values = ", ".join(f"'{root}'" for root in roots)
        clauses.append(f"(target_owner_module = '{owner}' AND target_object_type IN ({values}))")
    return (
        "(target_owner_module IS NULL AND target_object_type IS NULL "
        "AND target_object_id IS NULL AND target_version_id IS NULL) OR "
        "(target_owner_module IS NOT NULL AND target_object_type IS NOT NULL "
        "AND target_object_id IS NOT NULL AND (" + " OR ".join(clauses) + "))"
    )


def upgrade() -> None:
    op.create_table(
        "aud_events",
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("occurred_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_scope", sa.Text(), nullable=False),
        sa.Column("target_project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("original_actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_hint_digest", sa.LargeBinary()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("target_owner_module", sa.Text()),
        sa.Column("target_object_type", sa.Text()),
        sa.Column("target_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("target_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reason_code", sa.Text()),
        sa.Column("before_state", sa.Text()),
        sa.Column("after_state", sa.Text()),
        sa.CheckConstraint("event_scope IN ('DEPLOYMENT', 'PROJECT')", name="ck_aud_events__event_scope"),
        sa.CheckConstraint("(event_scope = 'DEPLOYMENT' AND target_project_id IS NULL) OR (event_scope = 'PROJECT' AND target_project_id IS NOT NULL)", name="ck_aud_events__project_scope"),
        sa.CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'UNRESOLVED')", name="ck_aud_events__actor_type"),
        sa.CheckConstraint("(actor_type = 'USER' AND actor_id IS NOT NULL AND original_actor_id IS NULL AND actor_hint_digest IS NULL) OR (actor_type = 'SYSTEM' AND actor_id IS NOT NULL AND original_actor_id IS NOT NULL AND actor_hint_digest IS NULL) OR (actor_type = 'UNRESOLVED' AND actor_id IS NULL AND original_actor_id IS NULL)", name="ck_aud_events__actor_shape"),
        sa.CheckConstraint("actor_hint_digest IS NULL OR octet_length(actor_hint_digest) = 32", name="ck_aud_events__actor_hint_digest"),
        sa.CheckConstraint("action ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__action"),
        sa.CheckConstraint("outcome IN ('SUCCESS', 'DENIED', 'FAILED')", name="ck_aud_events__outcome"),
        sa.CheckConstraint(_target_pair_check(), name="ck_aud_events__target_pair"),
        sa.CheckConstraint("reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__reason_code"),
        sa.CheckConstraint("before_state IS NULL OR before_state ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__before_state"),
        sa.CheckConstraint("after_state IS NULL OR after_state ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__after_state"),
        schema="plm",
    )
    op.create_index("ix_aud_events__project_time", "aud_events", ["target_project_id", sa.text("occurred_at DESC"), sa.text("audit_event_id DESC")], schema="plm")
    op.create_index("ix_aud_events__target_time", "aud_events", ["target_owner_module", "target_object_type", "target_object_id", "target_version_id", sa.text("occurred_at DESC")], schema="plm")
    op.create_index("ix_aud_events__actor_time", "aud_events", ["actor_id", sa.text("occurred_at DESC"), sa.text("audit_event_id DESC")], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.reject_audit_event_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_aud_events_no_update_delete
        BEFORE UPDATE OR DELETE ON plm.aud_events
        FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_event_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_aud_events_no_truncate
        BEFORE TRUNCATE ON plm.aud_events
        FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_event_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: audit events must be checked")
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM plm.aud_events")):
        raise RuntimeError("audit events exist; downgrade refused")
    op.execute("DROP TRIGGER trg_aud_events_no_truncate ON plm.aud_events")
    op.execute("DROP TRIGGER trg_aud_events_no_update_delete ON plm.aud_events")
    op.execute("DROP FUNCTION plm.reject_audit_event_mutation()")
    op.drop_index("ix_aud_events__actor_time", table_name="aud_events", schema="plm")
    op.drop_index("ix_aud_events__target_time", table_name="aud_events", schema="plm")
    op.drop_index("ix_aud_events__project_time", table_name="aud_events", schema="plm")
    op.drop_table("aud_events", schema="plm")
