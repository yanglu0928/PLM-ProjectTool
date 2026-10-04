"""LIC-02 derived validation state and append-only verification evidence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, LargeBinary, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


VALIDATION_CODES = "'VALID','NOT_INSTALLED','MALFORMED','SIGNATURE_INVALID','MACHINE_MISMATCH','NOT_YET_VALID','EXPIRED','TIME_ROLLBACK','PRODUCT_MISMATCH','TRUST_STATE_INVALID'"


class LicenseValidationEventRow(Base):
    __tablename__ = "lic_validation_events"
    __table_args__ = (
        CheckConstraint(f"validation_code IN ({VALIDATION_CODES})", name="ck_lic_validation_events__code"),
        CheckConstraint("machine_fingerprint_hash IS NULL OR octet_length(machine_fingerprint_hash) = 32", name="ck_lic_validation_events__fingerprint"),
        CheckConstraint("document_sha256 IS NULL OR octet_length(document_sha256) = 32", name="ck_lic_validation_events__document_sha256"),
        CheckConstraint("entitlement_snapshot IS NULL OR jsonb_typeof(entitlement_snapshot) = 'object'", name="ck_lic_validation_events__entitlement"),
        Index("ix_lic_validation_events__installation_time", "installation_id", "validated_at"),
    )

    validation_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    installation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    validation_code: Mapped[str] = mapped_column(Text, nullable=False)
    machine_fingerprint_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    document_sha256: Mapped[bytes | None] = mapped_column(LargeBinary)
    entitlement_snapshot: Mapped[Any | None] = mapped_column(JSONB)
    validated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LicenseValidationStateRow(Base):
    __tablename__ = "lic_validation_states"
    __table_args__ = (
        UniqueConstraint("singleton_key", name="uq_lic_validation_states__singleton"),
        CheckConstraint("singleton_key = 1", name="ck_lic_validation_states__singleton"),
        CheckConstraint(f"validation_code IN ({VALIDATION_CODES})", name="ck_lic_validation_states__code"),
        CheckConstraint("machine_fingerprint_hash IS NULL OR octet_length(machine_fingerprint_hash) = 32", name="ck_lic_validation_states__fingerprint"),
        CheckConstraint("entitlement_snapshot IS NULL OR jsonb_typeof(entitlement_snapshot) = 'object'", name="ck_lic_validation_states__entitlement"),
        CheckConstraint("state_version >= 0", name="ck_lic_validation_states__version"),
        CheckConstraint("validated_at IS NULL OR validated_at <= updated_at", name="ck_lic_validation_states__time"),
        CheckConstraint("validation_code <> 'VALID' OR (active_license_ref IS NOT NULL AND machine_fingerprint_hash IS NOT NULL AND current_event_ref IS NOT NULL AND entitlement_snapshot IS NOT NULL AND validated_at IS NOT NULL)", name="ck_lic_validation_states__valid_shape"),
        CheckConstraint("validation_code <> 'NOT_INSTALLED' OR active_license_ref IS NULL", name="ck_lic_validation_states__not_installed"),
    )

    license_validation_state_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    singleton_key: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    active_license_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.lic_installations.license_installation_id", ondelete="NO ACTION", name="fk_lic_validation_states__active_installation"), index=True)
    machine_fingerprint_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    validation_code: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'NOT_INSTALLED'"))
    entitlement_snapshot: Mapped[Any | None] = mapped_column(JSONB)
    validated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    current_event_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.lic_validation_events.validation_event_id", ondelete="NO ACTION", name="fk_lic_validation_states__event"), index=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
