"""Cross-module API replay receipts; never store raw keys or response bodies."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class IdempotencyReceiptRow(Base):
    __tablename__ = "plt_idempotency_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "project_id", "operation", "key_digest",
            name="uq_plt_idem_receipts__scope", postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("operation ~ '^V[1-9][0-9]*_[A-Z][A-Z0-9_]{2,120}$' AND char_length(operation) <= 128", name="ck_plt_idem_receipts__operation"),
        CheckConstraint("state IN ('PENDING', 'COMPLETED')", name="ck_plt_idem_receipts__state"),
        CheckConstraint("octet_length(key_digest) = 32", name="ck_plt_idem_receipts__key_digest"),
        CheckConstraint("octet_length(request_fingerprint) = 32", name="ck_plt_idem_receipts__fingerprint"),
        CheckConstraint("(state = 'PENDING' AND result_ref_type IS NULL AND result_ref_id IS NULL AND result_status IS NULL AND completed_at IS NULL) OR (state = 'COMPLETED' AND result_ref_type ~ '^V[1-9][0-9]*_[A-Z][A-Z0-9_]{2,120}$' AND char_length(result_ref_type) <= 128 AND result_ref_id IS NOT NULL AND result_status BETWEEN 200 AND 299 AND completed_at IS NOT NULL)", name="ck_plt_idem_receipts__result"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    key_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    result_ref_type: Mapped[str | None] = mapped_column(Text)
    result_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result_status: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
