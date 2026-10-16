"""PostgreSQL Outbox row locks, recovery and consumption dedupe."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.outbox import ClaimedEvent, OutboxDeliveryError
from plm_assistant.modules.jobs.infrastructure.orm import OutboxConsumptionRow, OutboxEventRow


class SqlAlchemyOutboxDeliveryRepository:
    def claim_next(self, transaction: object, *, owner_ref: str,
                   lease_seconds: int) -> ClaimedEvent | None:
        session = self._session(transaction)
        for _ in range(100):
            now = self._now(session)
            event = session.execute(select(OutboxEventRow).where(or_(
                and_(OutboxEventRow.delivery_state.in_(("PENDING", "RETRY_WAIT")),
                     OutboxEventRow.next_attempt_at <= now),
                and_(OutboxEventRow.delivery_state == "DELIVERING",
                     OutboxEventRow.delivery_expires_at <= now),
            )).order_by(OutboxEventRow.next_attempt_at, OutboxEventRow.event_id)
                .limit(1).with_for_update(of=OutboxEventRow, skip_locked=True)).scalar_one_or_none()
            if event is None:
                return None
            if event.attempt_count >= event.max_attempts:
                event.delivery_state = "DEAD"
                event.delivery_owner = None
                event.delivery_expires_at = None
                event.last_error_code = "ATTEMPTS_EXHAUSTED"
                session.flush()
                continue
            if event.delivery_state == "DELIVERING":
                event.last_error_code = "LEASE_EXPIRED"
            event.attempt_count += 1
            event.delivery_token += 1
            event.delivery_state = "DELIVERING"
            event.delivery_owner = owner_ref
            event.delivery_expires_at = now + timedelta(seconds=lease_seconds)
            session.flush()
            return self._claim(event)
        raise OutboxDeliveryError("CLAIM_BATCH_LIMIT")

    def heartbeat(self, transaction: object, *, event_id: uuid.UUID,
                  delivery_token: int, owner_ref: str, lease_seconds: int) -> None:
        session = self._session(transaction)
        event = self._current(session, event_id, delivery_token, owner_ref)
        event.delivery_expires_at = self._now(session) + timedelta(seconds=lease_seconds)
        session.flush()

    def acknowledge(self, transaction: object, *, event_id: uuid.UUID,
                    delivery_token: int, owner_ref: str, consumer_id: str,
                    consume: Callable[[object, ClaimedEvent], None]) -> bool:
        session = self._session(transaction)
        event = self._current(session, event_id, delivery_token, owner_ref)
        existing = session.execute(select(OutboxConsumptionRow.consumer_id).where(
            OutboxConsumptionRow.event_id == event_id,
        ).with_for_update(of=OutboxConsumptionRow)).scalar_one_or_none()
        if existing is not None and existing != consumer_id:
            raise OutboxDeliveryError("CONSUMER_MISMATCH")
        consumed = existing is None
        if consumed:
            session.add(OutboxConsumptionRow(event_id=event_id, consumer_id=consumer_id))
            session.flush()
            consume(transaction, self._claim(event))
        event.delivery_state = "DELIVERED"
        event.delivery_owner = None
        event.delivery_expires_at = None
        event.delivered_at = self._now(session)
        event.last_error_code = None
        session.flush()
        return consumed

    def retry_or_dead(self, transaction: object, *, event_id: uuid.UUID,
                      delivery_token: int, owner_ref: str,
                      error_code: str, retryable: bool, delay_seconds: int) -> str:
        session = self._session(transaction)
        event = self._current(session, event_id, delivery_token, owner_ref)
        now = self._now(session)
        event.delivery_owner = None
        event.delivery_expires_at = None
        event.last_error_code = error_code
        if retryable and event.attempt_count < event.max_attempts:
            event.delivery_state = "RETRY_WAIT"
            event.next_attempt_at = now + timedelta(seconds=delay_seconds)
        else:
            event.delivery_state = "DEAD"
        session.flush()
        return event.delivery_state

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise OutboxDeliveryError("OUTBOX_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise OutboxDeliveryError("OUTBOX_STORE_UNAVAILABLE")
        return session

    @staticmethod
    def _now(session: Session):
        return session.execute(select(func.clock_timestamp())).scalar_one()

    @staticmethod
    def _claim(event: OutboxEventRow) -> ClaimedEvent:
        return ClaimedEvent(event.event_id, event.event_type, event.owner_module,
                            event.scope, event.project_id, event.aggregate_ref,
                            event.aggregate_version, dict(event.payload_refs),
                            event.trace_id, event.delivery_token, event.attempt_count)

    def _current(self, session: Session, event_id: uuid.UUID,
                 token: int, owner_ref: str) -> OutboxEventRow:
        event = session.execute(select(OutboxEventRow).where(
            OutboxEventRow.event_id == event_id,
        ).with_for_update(of=OutboxEventRow)).scalar_one_or_none()
        if event is None or event.delivery_state != "DELIVERING" or event.delivery_token != token or event.delivery_owner != owner_ref:
            raise OutboxDeliveryError("STALE_DELIVERY")
        now = self._now(session)
        if event.delivery_expires_at is None or event.delivery_expires_at <= now:
            raise OutboxDeliveryError("STALE_DELIVERY")
        return event
