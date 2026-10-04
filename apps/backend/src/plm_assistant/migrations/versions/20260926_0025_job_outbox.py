"""Durable Job, Attempt, Lease and Outbox foundations.

Revision ID: 20260926_0025
Revises: 20260925_0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260926_0025"
down_revision = "20260925_0024"
branch_labels = None
depends_on = None

_ID = postgresql.UUID(as_uuid=True)
_TIME = postgresql.TIMESTAMP(timezone=True, precision=6)


def _id(name: str, *, primary: bool = False, nullable: bool = False) -> sa.Column:
    return sa.Column(name, _ID, primary_key=primary, nullable=nullable,
                     server_default=sa.text("uuidv7()") if primary else None)


def _time(name: str, *, nullable: bool = False, default: bool = False) -> sa.Column:
    return sa.Column(name, _TIME, nullable=nullable,
                     server_default=sa.text("statement_timestamp()") if default else None)


def upgrade() -> None:
    op.create_table(
        "job_jobs", _id("job_id", primary=True),
        sa.Column("owner_module", sa.Text(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False), _id("project_id", nullable=True),
        _id("actor_ref", nullable=True), sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("payload_refs", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        _time("available_at", default=True), _time("lease_expires_at", nullable=True),
        _time("created_at", default=True), _time("completed_at", nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_job_jobs__project", ondelete="NO ACTION"),
        sa.UniqueConstraint("owner_module", "scope", "project_id", "job_type", "idempotency_key", name="uq_job_jobs__idempotency", postgresql_nulls_not_distinct=True),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", name="ck_job_jobs__scope"),
        sa.CheckConstraint("state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')", name="ck_job_jobs__state"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0 AND fencing_token >= 0", name="ck_job_jobs__counters"),
        schema="plm",
    )
    op.create_index("ix_job_jobs__claim", "job_jobs", [sa.text("priority DESC"), "available_at", "job_id"], schema="plm", postgresql_where=sa.text("state IN ('PENDING','RETRY_WAIT')"))
    op.create_index("ix_job_jobs__lease_expiry", "job_jobs", ["lease_expires_at", "job_id"], schema="plm", postgresql_where=sa.text("state='RUNNING'"))
    op.create_table(
        "job_attempts", _id("attempt_id", primary=True), _id("job_id"),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_ref", sa.Text(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        _time("started_at", default=True), _time("completed_at", nullable=True),
        sa.Column("error_code", sa.Text()),
        sa.ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"], name="fk_job_attempts__job", ondelete="NO ACTION"),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_job_attempts__number"),
        sa.CheckConstraint("attempt_no > 0 AND fencing_token > 0", name="ck_job_attempts__positive"),
        schema="plm",
    )
    op.create_table(
        "job_leases", _id("lease_id", primary=True), _id("job_id"),
        sa.Column("worker_ref", sa.Text(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        _time("acquired_at", default=True), _time("heartbeat_at", default=True),
        _time("lease_expires_at"),
        sa.ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"], name="fk_job_leases__job", ondelete="NO ACTION"),
        sa.UniqueConstraint("job_id", "fencing_token", name="uq_job_leases__token"),
        sa.CheckConstraint("state IN ('ACTIVE','RELEASED','EXPIRED')", name="ck_job_leases__state"),
        sa.CheckConstraint("fencing_token > 0 AND lease_expires_at > acquired_at", name="ck_job_leases__valid"),
        schema="plm",
    )
    op.create_index("uq_job_leases__job_active", "job_leases", ["job_id"], schema="plm", unique=True, postgresql_where=sa.text("state='ACTIVE'"))
    op.create_table(
        "job_outbox_events", _id("event_id", primary=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("owner_module", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False), _id("project_id", nullable=True),
        _id("aggregate_ref"), sa.Column("aggregate_version", sa.BigInteger(), nullable=False),
        sa.Column("payload_refs", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("delivery_state", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        _time("next_attempt_at", default=True), _time("created_at", default=True),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_job_outbox_events__project", ondelete="NO ACTION"),
        sa.UniqueConstraint("owner_module", "scope", "project_id", "event_type", "idempotency_key", name="uq_job_outbox_events__idempotency", postgresql_nulls_not_distinct=True),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", name="ck_job_outbox_events__scope"),
        sa.CheckConstraint("delivery_state IN ('PENDING','DELIVERING','DELIVERED','RETRY_WAIT','DEAD')", name="ck_job_outbox_events__state"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_job_outbox_events__attempts"),
        schema="plm",
    )
    op.create_index("ix_job_outbox__claim", "job_outbox_events", ["next_attempt_at", "event_id"], schema="plm", postgresql_where=sa.text("delivery_state IN ('PENDING','RETRY_WAIT')"))
    op.create_table(
        "job_outbox_consumptions", _id("consumption_id", primary=True), _id("event_id"),
        sa.Column("consumer_id", sa.Text(), nullable=False), _time("consumed_at", default=True),
        sa.ForeignKeyConstraint(["event_id"], ["plm.job_outbox_events.event_id"], name="fk_job_outbox_consumptions__event", ondelete="NO ACTION"),
        sa.UniqueConstraint("event_id", "consumer_id", name="uq_job_consumptions__event_consumer"),
        schema="plm",
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for Job/Outbox")
    bind = op.get_bind()
    for table in ("job_outbox_consumptions", "job_outbox_events", "job_leases", "job_attempts", "job_jobs"):
        if bind.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM plm.{table})")):
            raise RuntimeError(f"{table} history exists; downgrade refused")
    op.drop_table("job_outbox_consumptions", schema="plm")
    op.drop_index("ix_job_outbox__claim", table_name="job_outbox_events", schema="plm")
    op.drop_table("job_outbox_events", schema="plm")
    op.drop_index("uq_job_leases__job_active", table_name="job_leases", schema="plm")
    op.drop_table("job_leases", schema="plm")
    op.drop_table("job_attempts", schema="plm")
    op.drop_index("ix_job_jobs__lease_expiry", table_name="job_jobs", schema="plm")
    op.drop_index("ix_job_jobs__claim", table_name="job_jobs", schema="plm")
    op.drop_table("job_jobs", schema="plm")
