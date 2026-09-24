"""PostgreSQL adapter for the internal trusted-time port."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.license.application.trusted_time import TrustedTimeRecord
from plm_assistant.modules.license.infrastructure.trusted_time_orm import TrustedTimeEventRow, TrustedTimeStateRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("active trusted-time transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active trusted-time transaction is required")
    return session


class SqlAlchemyTrustedTimeRepository:
    def read_locked(self, transaction: object) -> TrustedTimeRecord | None:
        row = _session(transaction).execute(
            select(TrustedTimeStateRow).where(TrustedTimeStateRow.singleton_key == 1).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return None
        return TrustedTimeRecord(row.trusted_time_state_id, row.last_successful_time,
                                 row.state_version, row.integrity_metadata,
                                 row.last_success_event_ref)

    def append_event(self, transaction: object, *, code: str, candidate: datetime,
                     trace_id: uuid.UUID) -> uuid.UUID:
        return _session(transaction).execute(
            insert(TrustedTimeEventRow).values(event_code=code, candidate_time=candidate,
                                               trace_id=trace_id).returning(TrustedTimeEventRow.trusted_time_event_id)
        ).scalar_one()

    def advance(self, transaction: object, *, expected_version: int, state_id: uuid.UUID,
                candidate: datetime, event_id: uuid.UUID,
                integrity_metadata: dict[str, str]) -> bool:
        result = _session(transaction).execute(
            update(TrustedTimeStateRow).where(
                TrustedTimeStateRow.trusted_time_state_id == state_id,
                TrustedTimeStateRow.singleton_key == 1,
                TrustedTimeStateRow.state_version == expected_version,
            ).values(last_successful_time=candidate,
                     state_version=expected_version + 1,
                     integrity_metadata=integrity_metadata,
                     last_success_event_ref=event_id,
                     updated_at=candidate)
        )
        return result.rowcount == 1
