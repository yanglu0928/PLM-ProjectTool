"""Licensed administrator-only Secret metadata queries without sensitive values."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


class SecretMetadataError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SecretMetadataView:
    secret_id: uuid.UUID
    purpose: str
    state: str
    allowed_consumer: str
    current_version_no: int | None
    created_at: datetime
    updated_at: datetime
    lock_version: int


@dataclass(frozen=True, slots=True)
class SecretMetadataQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


class DeploymentReadAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SecretMetadataRepositoryPort(Protocol):
    def get(self, transaction: object, secret_id: uuid.UUID) -> SecretMetadataView | None: ...
    def list_page(self, transaction: object, *, after: uuid.UUID | None,
                  limit: int) -> list[SecretMetadataView]: ...
    def list_http_page(self, transaction: object, *,
                       after: tuple[datetime, uuid.UUID] | None,
                       limit: int) -> list[SecretMetadataView]: ...


class SecretMetadataService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: DeploymentReadAccessPort,
                 license_guard: LicenseGuardPort, repository: SecretMetadataRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository)):
            raise ValueError("secret metadata dependencies are required")
        self._unit_of_work, self._access = unit_of_work, access
        self._license_guard, self._repository = license_guard, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: SecretMetadataQuery, secret_id: uuid.UUID) -> SecretMetadataView:
        if type(secret_id) is not uuid.UUID or secret_id.int == 0:
            raise SecretMetadataError("VALIDATION_FAILED")
        return self._query(query, lambda tx: self._repository.get(tx, secret_id), single=True)

    def list_page(self, query: SecretMetadataQuery, *, after: uuid.UUID | None = None,
                  limit: int = 50) -> list[SecretMetadataView]:
        if ((after is not None and (type(after) is not uuid.UUID or after.int == 0))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise SecretMetadataError("VALIDATION_FAILED")
        return self._query(query, lambda tx: self._repository.list_page(tx, after=after, limit=limit),
                           single=False)

    def list_http_page(self, query: SecretMetadataQuery, *,
                       after: tuple[datetime, uuid.UUID] | None = None,
                       limit: int = 51) -> list[SecretMetadataView]:
        if (type(limit) is not int or not 1 <= limit <= 201
                or (after is not None and (
                    type(after) is not tuple or len(after) != 2
                    or not isinstance(after[0], datetime) or after[0].tzinfo is None
                    or after[0].utcoffset() is None
                    or type(after[1]) is not uuid.UUID or after[1].int == 0))):
            raise SecretMetadataError("VALIDATION_FAILED")
        return self._query(
            query, lambda tx: self._repository.list_http_page(tx, after=after, limit=limit),
            single=False,
        )

    def _query(self, query: SecretMetadataQuery, reader: Callable[[object], object],
               *, single: bool):
        if (type(query) is not SecretMetadataQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise SecretMetadataError("VALIDATION_FAILED")
        try:
            with self._unit_of_work() as tx:
                self._require_admin(tx, query)
            self._license_guard.require_valid(trace_id=query.trace_id)
            with self._unit_of_work() as tx:
                self._require_admin(tx, query)
                value = reader(tx)
                if single and value is None:
                    raise SecretMetadataError("SECRET_NOT_FOUND")
                return value
        except SecretMetadataError:
            raise
        except Exception:
            raise SecretMetadataError("SECRET_UNAVAILABLE") from None

    def _require_admin(self, tx: object, query: SecretMetadataQuery) -> None:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise SecretMetadataError("SECRET_UNAVAILABLE")
        actor = self._access.authorized_admin(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SecretMetadataError("AUTH_ACCESS_DENIED")
