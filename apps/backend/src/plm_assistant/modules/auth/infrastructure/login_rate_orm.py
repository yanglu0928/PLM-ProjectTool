"""Short-lived, digest-keyed login attempt windows (no raw identity/address)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, LargeBinary
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class LoginRateBucketRow(Base):
    __tablename__ = "auth_login_rate_buckets"
    __table_args__ = (
        CheckConstraint("octet_length(bucket_key) = 32", name="ck_auth_login_rate_buckets__key_size"),
        CheckConstraint("attempt_count BETWEEN 1 AND 30", name="ck_auth_login_rate_buckets__count"),
        CheckConstraint("last_attempt_at >= window_started_at", name="ck_auth_login_rate_buckets__time"),
        Index("ix_auth_login_rate_buckets__last_attempt", "last_attempt_at"),
    )

    bucket_key: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    last_attempt_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
