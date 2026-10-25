"""AI-02 deployment model identities; no model routing or provider call."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class AIModelRow(Base):
    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("ai_provider_id", "provider_model_key", "model_kind", "model_revision", "embedding_dimension",
                         name="uq_ai_models__semantic_identity", postgresql_nulls_not_distinct=True),
        CheckConstraint(
            "ai_model_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND created_by <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_ai_models__ids",
        ),
        CheckConstraint("provider_model_key ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'", name="ck_ai_models__key"),
        CheckConstraint("model_revision = 'PROVIDER_MANAGED' OR model_revision ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'",
                        name="ck_ai_models__revision"),
        CheckConstraint("model_kind IN ('CHAT','EMBEDDING','RERANK')", name="ck_ai_models__kind"),
        CheckConstraint("(model_kind = 'EMBEDDING' AND embedding_dimension IS NOT NULL "
                        "AND embedding_dimension BETWEEN 1 AND 65536) "
                        "OR (model_kind <> 'EMBEDDING' AND embedding_dimension IS NULL)",
                        name="ck_ai_models__dimension"),
        CheckConstraint("model_state IN ('AVAILABLE','SUSPENDED','RETIRED') AND lock_version >= 0",
                        name="ck_ai_models__state"),
        CheckConstraint("isfinite(created_at)", name="ck_ai_models__time"),
        Index("ix_ai_models__provider_state", "ai_provider_id", "model_state", "ai_model_id"),
    )

    ai_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.ai_providers.ai_provider_id", ondelete="NO ACTION"), nullable=False)
    provider_model_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_kind: Mapped[str] = mapped_column(Text, nullable=False)
    model_revision: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    model_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'SUSPENDED'"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                 server_default=text("statement_timestamp()"))


class AIModelCapabilityRow(Base):
    __tablename__ = "ai_model_capabilities"
    __table_args__ = (
        CheckConstraint("capability_code IN ('STRUCTURED_OUTPUT','CONTEXT_WINDOW_TOKENS')",
                        name="ck_ai_model_capabilities__code"),
        CheckConstraint("(capability_code = 'STRUCTURED_OUTPUT' AND value_bool IS NOT NULL AND value_integer IS NULL) "
                        "OR (capability_code = 'CONTEXT_WINDOW_TOKENS' AND value_bool IS NULL "
                        "AND value_integer IS NOT NULL AND value_integer BETWEEN 1 AND 1048576)",
                        name="ck_ai_model_capabilities__value"),
    )
    ai_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.ai_models.ai_model_id", ondelete="NO ACTION"), primary_key=True)
    capability_code: Mapped[str] = mapped_column(Text, primary_key=True)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_integer: Mapped[int | None] = mapped_column(Integer)


class AIQualityProfileRefRow(Base):
    __tablename__ = "ai_quality_profile_refs"
    __table_args__ = (
        CheckConstraint("quality_profile_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
                        name="ck_ai_quality_profile_refs__ref"),
        CheckConstraint("isfinite(linked_at)", name="ck_ai_quality_profile_refs__time"),
        Index("ix_ai_quality_profile_refs__profile", "quality_profile_ref"),
    )
    ai_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.ai_models.ai_model_id", ondelete="NO ACTION"), primary_key=True)
    quality_profile_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                server_default=text("statement_timestamp()"))


class AIModelStateResultRow(Base):
    __tablename__ = "ai_model_state_results"
    __table_args__ = (
        UniqueConstraint("ai_model_id", "lock_version",
                         name="uq_ai_model_state_results__model_version"),
        UniqueConstraint("audit_event_id", name="uq_ai_model_state_results__audit"),
        CheckConstraint(
            "state_result_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ai_model_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND audit_event_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND trace_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ((operation = 'SUSPEND' AND before_state = 'AVAILABLE' AND result_state = 'SUSPENDED') "
            "OR (operation = 'RETIRE' AND before_state IN ('AVAILABLE','SUSPENDED') "
            "AND result_state = 'RETIRED')) "
            "AND expected_lock_version BETWEEN 0 AND 9223372036854775806 "
            "AND lock_version = expected_lock_version + 1 "
            "AND created_xid > 0 AND isfinite(accepted_at)",
            name="ck_ai_model_state_results__shape",
        ),
    )

    state_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ai_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.ai_models.ai_model_id", ondelete="NO ACTION"), nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False,
    )
    audit_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plm.aud_events.audit_event_id", ondelete="NO ACTION"), nullable=False,
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[str] = mapped_column(Text, nullable=False)
    result_state: Mapped[str] = mapped_column(Text, nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )
