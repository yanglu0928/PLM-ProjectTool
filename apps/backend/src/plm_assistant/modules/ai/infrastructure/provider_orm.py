"""AI-01 deployment Provider identity and immutable configuration history."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class AIProviderRow(Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        CheckConstraint("provider_state IN ('CONFIGURED','ACTIVE','SUSPENDED','RETIRED') AND lock_version >= 0", name="ck_ai_providers__state"),
        CheckConstraint("ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid AND current_config_version_ref <> '00000000-0000-0000-0000-000000000000'::uuid", name="ck_ai_providers__ids"),
        ForeignKeyConstraint(
            ["current_config_version_ref", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id", "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_providers__current_config", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        Index("ix_ai_providers__current_config", "current_config_version_ref", "ai_provider_id"),
    )

    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    current_config_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'CONFIGURED'"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))


class AIProviderConfigVersionRow(Base):
    __tablename__ = "ai_provider_config_versions"
    __table_args__ = (
        UniqueConstraint("provider_config_version_id", "ai_provider_id", name="uq_ai_provider_configs__id_provider"),
        UniqueConstraint("ai_provider_id", "config_version_no", name="uq_ai_provider_configs__provider_no"),
        CheckConstraint("provider_config_version_id <> '00000000-0000-0000-0000-000000000000'::uuid AND ai_provider_id <> '00000000-0000-0000-0000-000000000000'::uuid AND secret_ref <> '00000000-0000-0000-0000-000000000000'::uuid", name="ck_ai_provider_configs__ids"),
        CheckConstraint("config_version_no > 0 AND created_xid > 0", name="ck_ai_provider_configs__version"),
        CheckConstraint("provider_kind IN ('OPENAI_COMPATIBLE','ANTHROPIC_MESSAGES','GEMINI_NATIVE','CUSTOM')", name="ck_ai_provider_configs__kind"),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 120 AND char_length(btrim(display_name)) > 0", name="ck_ai_provider_configs__display_name"),
        CheckConstraint("char_length(endpoint_policy_ref) BETWEEN 1 AND 128 AND endpoint_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:-]*$'", name="ck_ai_provider_configs__endpoint_ref"),
        CheckConstraint("char_length(data_region) BETWEEN 1 AND 64 AND data_region ~ '^[a-z][a-z0-9-]*$'", name="ck_ai_provider_configs__region"),
        CheckConstraint("char_length(egress_class) BETWEEN 1 AND 64 AND egress_class ~ '^[A-Z][A-Z0-9_]*$'", name="ck_ai_provider_configs__egress"),
        CheckConstraint("can_chat OR can_structured_output OR can_embedding OR can_rerank", name="ck_ai_provider_configs__capabilities"),
        Index("ix_ai_provider_configs__secret", "secret_ref"),
        Index("ix_ai_provider_configs__creator", "created_by"),
    )

    provider_config_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    ai_provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.ai_providers.ai_provider_id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"), nullable=False)
    config_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_kind: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    secret_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.plt_secret_records.secret_record_id", ondelete="NO ACTION"), nullable=False)
    data_region: Mapped[str] = mapped_column(Text, nullable=False)
    egress_class: Mapped[str] = mapped_column(Text, nullable=False)
    can_chat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_structured_output: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_rerank: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("txid_current()"))
