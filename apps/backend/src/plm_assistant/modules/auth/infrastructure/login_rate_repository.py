"""Atomic PostgreSQL login window reservation; DB time is authoritative."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.login_rate_orm import LoginRateBucketRow


class SqlAlchemyLoginRateRepository:
    def reserve(self, transaction: object, *, bucket_key: bytes, limit: int,
                window: timedelta) -> bool:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active login rate transaction is required")
        if (type(bucket_key) is not bytes or len(bucket_key) != 32
                or type(limit) is not int or not 1 <= limit <= 30
                or type(window) is not timedelta or not timedelta(0) < window <= timedelta(hours=1)):
            raise ValueError("invalid login rate policy")
        now = func.statement_timestamp()
        expired = LoginRateBucketRow.window_started_at <= now - window
        statement = insert(LoginRateBucketRow).values(
            bucket_key=bucket_key, window_started_at=now,
            last_attempt_at=now, attempt_count=1,
        ).on_conflict_do_update(
            index_elements=[LoginRateBucketRow.bucket_key],
            set_={
                "window_started_at": case((expired, now), else_=LoginRateBucketRow.window_started_at),
                "last_attempt_at": now,
                "attempt_count": case((expired, 1), else_=LoginRateBucketRow.attempt_count + 1),
            },
            where=or_(expired, LoginRateBucketRow.attempt_count < limit),
        ).returning(LoginRateBucketRow.attempt_count)
        return session.execute(statement).scalar_one_or_none() is not None
