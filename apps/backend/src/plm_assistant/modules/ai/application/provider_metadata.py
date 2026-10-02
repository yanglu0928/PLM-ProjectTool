"""DeploymentAdmin-only AI Provider metadata detail, without Secret values."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class AIProviderMetadataError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIProviderMetadataQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AIProviderMetadataView:
    provider_id: uuid.UUID
    kind: ProviderKind
    display_name: str
    endpoint_policy_ref: str
    data_region: str
    egress_class: str
    capabilities: frozenset[ProviderCapability]
    secret_ref_masked: str
    state: str
    config_version: int
    lock_version: int

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


@dataclass(frozen=True, slots=True)
class AIProviderMetadataEntry:
    created_at: datetime
    view: AIProviderMetadataView


@dataclass(frozen=True, slots=True)
class AIProviderMetadataPage:
    items: tuple[AIProviderMetadataView, ...]
    next_cursor: str | None
    has_more: bool


class AIProviderReadAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class AIProviderReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIProviderMetadataRepositoryPort(Protocol):
    def get(self, transaction: object, *, provider_id: uuid.UUID) -> AIProviderMetadataView | None: ...
    def list_page(self, transaction: object, *, after: tuple[datetime, uuid.UUID] | None,
                  limit: int) -> list[AIProviderMetadataEntry]: ...


class AIProviderMetadataService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: AIProviderReadAccessPort, license_guard: AIProviderReadLicensePort,
                 repository: AIProviderMetadataRepositoryPort,
                 cursors: ProviderListCursorCodec | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository)):
            raise ValueError("AI Provider metadata dependencies are required")
        self._uow, self._access = unit_of_work, access
        self._guard, self._repo = license_guard, repository
        self._cursors = cursors
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: AIProviderMetadataQuery, provider_id: uuid.UUID) -> AIProviderMetadataView:
        self._validate(query)
        if type(provider_id) is not uuid.UUID or provider_id.int == 0:
            raise AIProviderMetadataError("VALIDATION_FAILED")
        try:
            with self._uow() as tx:
                self._require_admin(tx, query)
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._require_admin(tx, query)
                view = self._repo.get(tx, provider_id=provider_id)
                if view is None:
                    raise AIProviderMetadataError("RESOURCE_NOT_FOUND")
                if type(view) is not AIProviderMetadataView:
                    raise AIProviderMetadataError("AI_PROVIDER_UNAVAILABLE")
                return view
        except AIProviderMetadataError:
            raise
        except RuntimeLicenseError:
            raise AIProviderMetadataError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AIProviderMetadataError("AI_PROVIDER_UNAVAILABLE") from None

    def list_page(self, query: AIProviderMetadataQuery, *, page_size: int = 50,
                  cursor: str | None = None) -> AIProviderMetadataPage:
        self._validate(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (cursor is not None and type(cursor) is not str)):
            raise AIProviderMetadataError("VALIDATION_FAILED")
        if type(self._cursors) is not ProviderListCursorCodec:
            raise AIProviderMetadataError("AI_PROVIDER_UNAVAILABLE")
        try:
            with self._uow() as tx:
                self._require_admin(tx, query)
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._require_admin(tx, query)
                after = (self._cursors.decode(
                    cursor, session_token=query.session_token, page_size=page_size,
                ) if cursor is not None else None)
                rows = self._repo.list_page(tx, after=after, limit=page_size + 1)
                if (type(rows) is not list or len(rows) > page_size + 1
                        or any(type(row) is not AIProviderMetadataEntry
                               or type(row.view) is not AIProviderMetadataView for row in rows)):
                    raise AIProviderMetadataError("AI_PROVIDER_UNAVAILABLE")
                has_more = len(rows) > page_size
                page = rows[:page_size]
                next_cursor = (self._cursors.encode(
                    session_token=query.session_token, page_size=page_size,
                    created_at=page[-1].created_at, provider_id=page[-1].view.provider_id,
                ) if has_more else None)
                return AIProviderMetadataPage(tuple(row.view for row in page),
                                              next_cursor, has_more)
        except AIProviderMetadataError:
            raise
        except RuntimeLicenseError:
            raise AIProviderMetadataError("LICENSE_OPERATION_DENIED") from None
        except ValueError:
            raise AIProviderMetadataError("VALIDATION_FAILED") from None
        except Exception:
            raise AIProviderMetadataError("AI_PROVIDER_UNAVAILABLE") from None

    @staticmethod
    def _validate(query: AIProviderMetadataQuery) -> None:
        if (type(query) is not AIProviderMetadataQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise AIProviderMetadataError("VALIDATION_FAILED")

    def _require_admin(self, tx: object, query: AIProviderMetadataQuery) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIProviderMetadataError("AI_PROVIDER_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise AIProviderMetadataError("AUTH_ACCESS_DENIED")
        return actor_id
