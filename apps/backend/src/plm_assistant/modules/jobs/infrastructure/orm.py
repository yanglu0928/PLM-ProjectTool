"""Private Job/Outbox rows; payloads contain references, never source content."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class JobRow(Base):
    __tablename__ = "job_jobs"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_job_jobs__project", ondelete="NO ACTION"),
        UniqueConstraint("owner_module", "scope", "project_id", "job_type", "idempotency_key", name="uq_job_jobs__idempotency", postgresql_nulls_not_distinct=True),
        CheckConstraint("(scope IN ('GLOBAL','DEPLOYMENT') AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", name="ck_job_jobs__scope"),
        CheckConstraint("state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')", name="ck_job_jobs__state"),
        CheckConstraint("attempt_count >= 0 AND max_attempts > 0 AND fencing_token >= 0", name="ck_job_jobs__counters"),
        Index("ix_job_jobs__claim", text("priority DESC"), "available_at", "job_id", postgresql_where=text("state IN ('PENDING','RETRY_WAIT')")),
        Index("ix_job_jobs__lease_expiry", "lease_expires_at", "job_id", postgresql_where=text("state='RUNNING'")),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lease_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class JobAttemptRow(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"], name="fk_job_attempts__job", ondelete="NO ACTION"),
        UniqueConstraint("job_id", "attempt_no", name="uq_job_attempts__number"),
        CheckConstraint("attempt_no > 0 AND fencing_token > 0", name="ck_job_attempts__positive"),
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_ref: Mapped[str] = mapped_column(Text, nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    error_code: Mapped[str | None] = mapped_column(Text)


class JobLeaseRow(Base):
    __tablename__ = "job_leases"
    __table_args__ = (
        ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"], name="fk_job_leases__job", ondelete="NO ACTION"),
        UniqueConstraint("job_id", "fencing_token", name="uq_job_leases__token"),
        Index("uq_job_leases__job_active", "job_id", unique=True, postgresql_where=text("state='ACTIVE'")),
        CheckConstraint("state IN ('ACTIVE','RELEASED','EXPIRED')", name="ck_job_leases__state"),
        CheckConstraint("fencing_token > 0 AND lease_expires_at > acquired_at", name="ck_job_leases__valid"),
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    worker_ref: Mapped[str] = mapped_column(Text, nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    acquired_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    heartbeat_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lease_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)


class OutboxEventRow(Base):
    __tablename__ = "job_outbox_events"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_job_outbox_events__project", ondelete="NO ACTION"),
        UniqueConstraint("owner_module", "scope", "project_id", "event_type", "idempotency_key", name="uq_job_outbox_events__idempotency", postgresql_nulls_not_distinct=True),
        CheckConstraint("(scope IN ('GLOBAL','DEPLOYMENT') AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", name="ck_job_outbox_events__scope"),
        CheckConstraint("delivery_state IN ('PENDING','DELIVERING','DELIVERED','RETRY_WAIT','DEAD')", name="ck_job_outbox_events__state"),
        CheckConstraint("attempt_count >= 0", name="ck_job_outbox_events__attempts"),
        CheckConstraint("max_attempts > 0 AND delivery_token >= 0", name="ck_job_outbox_events__delivery_counters"),
        CheckConstraint("(delivery_state='DELIVERING' AND delivery_owner IS NOT NULL AND delivery_expires_at IS NOT NULL) OR (delivery_state<>'DELIVERING' AND delivery_owner IS NULL AND delivery_expires_at IS NULL)", name="ck_job_outbox_events__lease_shape"),
        CheckConstraint("delivery_owner IS NULL OR (char_length(delivery_owner) BETWEEN 1 AND 128 AND delivery_owner=btrim(delivery_owner))", name="ck_job_outbox_events__delivery_owner"),
        CheckConstraint("last_error_code IS NULL OR char_length(last_error_code) BETWEEN 1 AND 64", name="ck_job_outbox_events__error"),
        Index("ix_job_outbox__claim", "next_attempt_at", "event_id", postgresql_where=text("delivery_state IN ('PENDING','RETRY_WAIT')")),
        Index("ix_job_outbox__lease_expiry", "delivery_expires_at", "event_id", postgresql_where=text("delivery_state='DELIVERING'")),
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    aggregate_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    delivery_token: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    delivery_owner: Mapped[str | None] = mapped_column(Text)
    delivery_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    next_attempt_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    delivered_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    last_error_code: Mapped[str | None] = mapped_column(Text)


class OutboxConsumptionRow(Base):
    __tablename__ = "job_outbox_consumptions"
    __table_args__ = (
        ForeignKeyConstraint(["event_id"], ["plm.job_outbox_events.event_id"], name="fk_job_outbox_consumptions__event", ondelete="NO ACTION"),
        UniqueConstraint("event_id", "consumer_id", name="uq_job_consumptions__event_consumer"),
    )
    consumption_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    consumer_id: Mapped[str] = mapped_column(Text, nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
