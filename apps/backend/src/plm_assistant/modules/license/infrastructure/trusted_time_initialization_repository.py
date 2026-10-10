"""PostgreSQL one-time pristine trusted-time state creation."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from plm_assistant.modules.license.infrastructure.trusted_time_orm import (
    TrustedTimeEventRow, TrustedTimeStateRow,
)


class SqlAlchemyTrustedTimeInitializationRepository:
    def create_pristine(self, transaction: object) -> uuid.UUID | None:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active trusted-time initialization transaction is required")
        # No history may be present before initialization. This is not a reset path.
        session.execute(text("SELECT pg_advisory_xact_lock(7310303)"))
        session.execute(text("LOCK TABLE plm.lic_trusted_time_events IN SHARE MODE"))
        if session.execute(select(TrustedTimeEventRow.trusted_time_event_id).limit(1)).first():
            return None
        if session.execute(select(TrustedTimeStateRow.trusted_time_state_id).limit(1)).first():
            return None
        return session.execute(insert(TrustedTimeStateRow).values(
            singleton_key=1,
        ).on_conflict_do_nothing(
            index_elements=[TrustedTimeStateRow.singleton_key],
        ).returning(TrustedTimeStateRow.trusted_time_state_id)).scalar_one_or_none()
