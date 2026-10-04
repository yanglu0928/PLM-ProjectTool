"""PLT-02 encrypted Secret identity and version metadata; no plaintext columns."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class SecretRecordRow(Base):
    __tablename__ = "plt_secret_records"
    __table_args__ = (
        CheckConstraint("purpose IN ('DATABASE_PASSWORD','AI_PROVIDER_KEY','RERANKER_KEY','INTEGRATION_CREDENTIAL')", name="ck_plt_secret_records__purpose"),
        CheckConstraint("secret_state IN ('ACTIVE','DISABLED','RETIRED')", name="ck_plt_secret_records__state"),
        CheckConstraint("allowed_consumer IN ('DATABASE_ADAPTER','AI_PROVIDER_ADAPTER','RERANKER_ADAPTER','INTEGRATION_ADAPTER')", name="ck_plt_secret_records__consumer"),
        CheckConstraint("(purpose = 'DATABASE_PASSWORD' AND allowed_consumer = 'DATABASE_ADAPTER') OR (purpose = 'AI_PROVIDER_KEY' AND allowed_consumer = 'AI_PROVIDER_ADAPTER') OR (purpose = 'RERANKER_KEY' AND allowed_consumer = 'RERANKER_ADAPTER') OR (purpose = 'INTEGRATION_CREDENTIAL' AND allowed_consumer = 'INTEGRATION_ADAPTER')", name="ck_plt_secret_records__purpose_consumer"),
        CheckConstraint("lock_version >= 0", name="ck_plt_secret_records__lock_version"),
        CheckConstraint("secret_state <> 'ACTIVE' OR current_version_ref IS NOT NULL", name="ck_plt_secret_records__active_ref"),
        ForeignKeyConstraint(
            ["current_version_ref", "secret_record_id"],
            ["plm.plt_secret_versions.secret_version_id", "plm.plt_secret_versions.secret_record_id"],
            name="fk_plt_secret_records__current_version", ondelete="NO ACTION", use_alter=True,
        ),
    )

    secret_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    secret_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DISABLED'"))
    allowed_consumer: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class SecretVersionRow(Base):
    __tablename__ = "plt_secret_versions"
    __table_args__ = (
        UniqueConstraint("secret_record_id", "version_no", name="uq_plt_secret_versions__record_no"),
        UniqueConstraint("secret_version_id", "secret_record_id", name="uq_plt_secret_versions__identity_parent"),
        Index("uq_plt_secret_versions__record_active", "secret_record_id", unique=True,
              postgresql_where=text("activated_at IS NOT NULL AND retired_at IS NULL")),
        CheckConstraint("version_no > 0", name="ck_plt_secret_versions__version_no"),
        CheckConstraint("octet_length(encrypted_payload) BETWEEN 1 AND 65536", name="ck_plt_secret_versions__cipher_size"),
        CheckConstraint("jsonb_typeof(encryption_metadata) = 'object'", name="ck_plt_secret_versions__metadata"),
        CheckConstraint("char_length(key_provider_ref) BETWEEN 1 AND 128 AND key_provider_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$'", name="ck_plt_secret_versions__key_ref"),
        CheckConstraint("retired_at IS NULL OR (activated_at IS NOT NULL AND retired_at >= activated_at)", name="ck_plt_secret_versions__lifecycle"),
    )

    secret_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    secret_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.plt_secret_records.secret_record_id", ondelete="NO ACTION"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_metadata: Mapped[Any] = mapped_column(JSONB, nullable=False)
    key_provider_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    activated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    retired_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
