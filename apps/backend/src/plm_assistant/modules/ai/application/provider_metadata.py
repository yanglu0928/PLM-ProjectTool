"""DeploymentAdmin-only AI Provider metadata detail, without Secret values."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

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


class AIProviderReadAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class AIProviderReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIProviderMetadataRepositoryPort(Protocol):
    def get(self, transaction: object, *, provider_id: uuid.UUID) -> AIProviderMetadataView | None: ...


class AIProviderMetadataService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: AIProviderReadAccessPort, license_guard: AIProviderReadLicensePort,
                 repository: AIProviderMetadataRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository)):
            raise ValueError("AI Provider metadata dependencies are required")
        self._uow, self._access = unit_of_work, access
        self._guard, self._repo = license_guard, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: AIProviderMetadataQuery, provider_id: uuid.UUID) -> AIProviderMetadataView:
        if (type(query) is not AIProviderMetadataQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(provider_id) is not uuid.UUID or provider_id.int == 0):
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
