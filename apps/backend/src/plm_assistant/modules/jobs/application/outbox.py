"""At-least-once Outbox delivery with fenced acknowledgement."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from re import fullmatch
from typing import Protocol


class OutboxDeliveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ClaimedEvent:
    event_id: uuid.UUID
    event_type: str
    owner_module: str
    scope: str
    project_id: uuid.UUID | None
    aggregate_ref: uuid.UUID
    aggregate_version: int
    payload_refs: dict
    trace_id: str
    delivery_token: int
    attempt_count: int


class OutboxDeliveryRepositoryPort(Protocol):
    def claim_next(self, transaction: object, *, owner_ref: str,
                   lease_seconds: int) -> ClaimedEvent | None: ...
    def heartbeat(self, transaction: object, *, event_id: uuid.UUID,
                  delivery_token: int, owner_ref: str, lease_seconds: int) -> None: ...
    def acknowledge(self, transaction: object, *, event_id: uuid.UUID,
                    delivery_token: int, owner_ref: str,
                    consumer_id: str, consume: Callable[[object, ClaimedEvent], None]) -> bool: ...
    def retry_or_dead(self, transaction: object, *, event_id: uuid.UUID,
                      delivery_token: int, owner_ref: str,
                      error_code: str, retryable: bool, delay_seconds: int) -> str: ...


class OutboxDeliveryService:
    """Public to internal Worker only; handlers must perform short DB work."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: OutboxDeliveryRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("Outbox delivery dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository

    def claim_next(self, *, owner_ref: str, lease_seconds: int) -> ClaimedEvent | None:
        self._identity(owner_ref)
        self._lease_seconds(lease_seconds)
        with self._unit_of_work() as tx:
            result = self._repository.claim_next(tx, owner_ref=owner_ref,
                                                 lease_seconds=lease_seconds)
            tx.commit()
            return result

    def heartbeat(self, *, event_id: uuid.UUID, delivery_token: int,
                  owner_ref: str, lease_seconds: int) -> None:
        self._identity(owner_ref)
        self._lease_seconds(lease_seconds)
        with self._unit_of_work() as tx:
            self._repository.heartbeat(tx, event_id=event_id,
                                       delivery_token=delivery_token,
                                       owner_ref=owner_ref,
                                       lease_seconds=lease_seconds)
            tx.commit()

    def acknowledge(self, *, event_id: uuid.UUID, delivery_token: int,
                    owner_ref: str, consumer_id: str,
                    consume: Callable[[object, ClaimedEvent], None]) -> bool:
        self._identity(owner_ref)
        self._identity(consumer_id)
        if consume is None:
            raise OutboxDeliveryError("CONSUMER_REQUIRED")
        with self._unit_of_work() as tx:
            consumed = self._repository.acknowledge(
                tx, event_id=event_id, delivery_token=delivery_token,
                owner_ref=owner_ref, consumer_id=consumer_id, consume=consume,
            )
            tx.commit()
            return consumed

    def retry_or_dead(self, *, event_id: uuid.UUID, delivery_token: int,
                      owner_ref: str, error_code: str, retryable: bool,
                      delay_seconds: int = 0) -> str:
        self._identity(owner_ref)
        if not isinstance(error_code, str) or not fullmatch(r"[A-Z][A-Z0-9_]{0,63}", error_code):
            raise OutboxDeliveryError("INVALID_ERROR_CODE")
        if not 0 <= delay_seconds <= 86_400:
            raise OutboxDeliveryError("INVALID_RETRY_DELAY")
        with self._unit_of_work() as tx:
            state = self._repository.retry_or_dead(
                tx, event_id=event_id, delivery_token=delivery_token,
                owner_ref=owner_ref, error_code=error_code,
                retryable=retryable, delay_seconds=delay_seconds,
            )
            tx.commit()
            return state

    @staticmethod
    def _identity(value: str) -> None:
        if not isinstance(value, str) or not fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
            raise OutboxDeliveryError("INVALID_IDENTITY")

    @staticmethod
    def _lease_seconds(value: int) -> None:
        if not isinstance(value, int) or not 1 <= value <= 3600:
            raise OutboxDeliveryError("INVALID_LEASE_DURATION")
