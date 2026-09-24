"""Deployment-scoped trusted-time persistence; validation belongs to LicenseService."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class TrustedTimeEventRow(Base):
    __tablename__ = "lic_trusted_time_events"
    __table_args__ = (
        CheckConstraint("length(btrim(event_code)) BETWEEN 1 AND 64", name="ck_lic_trusted_time_events__code"),
        CheckConstraint("details IS NULL OR jsonb_typeof(details) = 'object'", name="ck_lic_trusted_time_events__details"),
    )

    trusted_time_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    event_code: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    candidate_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    details: Mapped[Any | None] = mapped_column(JSONB)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class TrustedTimeStateRow(Base):
    __tablename__ = "lic_trusted_time_states"
    __table_args__ = (
        UniqueConstraint("singleton_key", name="uq_lic_trusted_time_states__singleton"),
        CheckConstraint("singleton_key = 1", name="ck_lic_trusted_time_states__singleton"),
        CheckConstraint("state_version >= 0", name="ck_lic_trusted_time_states__version"),
        CheckConstraint("integrity_metadata IS NULL OR jsonb_typeof(integrity_metadata) = 'object'", name="ck_lic_trusted_time_states__integrity"),
        CheckConstraint("(last_successful_time IS NULL AND state_version = 0 AND integrity_metadata IS NULL AND last_success_event_ref IS NULL) OR (last_successful_time IS NOT NULL AND state_version > 0 AND integrity_metadata IS NOT NULL AND last_success_event_ref IS NOT NULL)", name="ck_lic_trusted_time_states__shape"),
        CheckConstraint("last_successful_time IS NULL OR updated_at >= last_successful_time", name="ck_lic_trusted_time_states__time"),
    )

    trusted_time_state_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    singleton_key: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    last_successful_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    integrity_metadata: Mapped[Any | None] = mapped_column(JSONB)
    last_success_event_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.lic_trusted_time_events.trusted_time_event_id", ondelete="NO ACTION", name="fk_lic_trusted_time_states__event"), index=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
