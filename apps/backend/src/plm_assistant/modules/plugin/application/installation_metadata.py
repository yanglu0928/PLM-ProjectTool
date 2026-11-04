"""DeploymentAdmin-only read projection for one Plugin installation."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class PluginInstallationMetadataError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PluginInstallationMetadataQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PluginOperationMetadata:
    operation_id: str
    output_types: tuple[str, ...]
    plugin_api_version: str


@dataclass(frozen=True, slots=True)
class PluginInstallationMetadataView:
    plugin_installation_id: uuid.UUID
    plugin_package_id: uuid.UUID
    plugin_id: str
    plugin_name: str
    plugin_version: str
    package_sha256: str
    package_state: str
    plugin_api_version: str
    supported_os: tuple[str, ...]
    architecture: str
    operations: tuple[PluginOperationMetadata, ...]
    installation_state: str
    compatibility_state: str
    runtime_snapshot: dict = field(repr=False)
    enabled_operations: tuple[str, ...]
    lock_version: int

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


class PluginInstallationReadAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class PluginInstallationReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PluginInstallationMetadataRepositoryPort(Protocol):
    def get(
        self, transaction: object, *, installation_id: uuid.UUID,
    ) -> PluginInstallationMetadataView | None: ...


class PluginInstallationMetadataService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: PluginInstallationReadAccessPort,
        license_guard: PluginInstallationReadLicensePort,
        repository: PluginInstallationMetadataRepositoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository)):
            raise ValueError("Plugin installation metadata dependencies are required")
        self._uow, self._access, self._guard, self._repository = (
            unit_of_work, access, license_guard, repository,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(
        self, query: PluginInstallationMetadataQuery, installation_id: uuid.UUID,
    ) -> PluginInstallationMetadataView:
        self._validate_query(query)
        if type(installation_id) is not uuid.UUID or installation_id.int == 0:
            raise PluginInstallationMetadataError("VALIDATION_FAILED")
        try:
            with self._uow() as transaction:
                self._require_admin(transaction, query)
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                self._require_admin(transaction, query)
                view = self._repository.get(
                    transaction, installation_id=installation_id,
                )
                if view is None:
                    raise PluginInstallationMetadataError("RESOURCE_NOT_FOUND")
                self._validate_view(view, installation_id)
                return view
        except PluginInstallationMetadataError:
            raise
        except RuntimeLicenseError:
            raise PluginInstallationMetadataError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PluginInstallationMetadataError(
                "PLUGIN_INSTALLATION_UNAVAILABLE"
            ) from None

    @staticmethod
    def _validate_query(query: object) -> None:
        if (type(query) is not PluginInstallationMetadataQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise PluginInstallationMetadataError("VALIDATION_FAILED")

    def _require_admin(
        self, transaction: object, query: PluginInstallationMetadataQuery,
    ) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        actor = self._access.authorized_admin(
            transaction, session_token=query.session_token, now=now,
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PluginInstallationMetadataError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _validate_view(
        view: object, installation_id: uuid.UUID,
    ) -> None:
        if (type(view) is not PluginInstallationMetadataView
                or view.plugin_installation_id != installation_id
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    view.plugin_installation_id, view.plugin_package_id,
                ))
                or type(view.plugin_id) is not str
                or not 2 <= len(view.plugin_id) <= 128
                or view.plugin_id != view.plugin_id.lower()
                or type(view.plugin_name) is not str or not 1 <= len(view.plugin_name) <= 256
                or type(view.plugin_version) is not str
                or not 1 <= len(view.plugin_version) <= 64
                or type(view.package_sha256) is not str
                or len(view.package_sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in view.package_sha256)
                or view.package_state not in {"VERIFIED", "REVOKED", "REJECTED", "IMPORTED"}
                or type(view.plugin_api_version) is not str
                or not 1 <= len(view.plugin_api_version) <= 32
                or type(view.supported_os) is not tuple
                or not 1 <= len(view.supported_os) <= 3
                or any(item not in {"windows-11", "windows-server-2025", "debian-13"}
                       for item in view.supported_os)
                or view.architecture != "x86_64"
                or type(view.operations) is not tuple or len(view.operations) > 256
                or any(type(item) is not PluginOperationMetadata
                       or not 1 <= len(item.operation_id) <= 255
                       or type(item.output_types) is not tuple or len(item.output_types) > 32
                       or type(item.plugin_api_version) is not str
                       for item in view.operations)
                or view.installation_state not in {
                    "INSTALLED", "ENABLED", "DISABLED", "INCOMPATIBLE", "RETIRED",
                }
                or view.compatibility_state not in {"COMPATIBLE", "INCOMPATIBLE"}
                or type(view.runtime_snapshot) is not dict
                or type(view.enabled_operations) is not tuple
                or len(view.enabled_operations) > 256
                or any(type(item) is not str for item in view.enabled_operations)
                or type(view.lock_version) is not int or view.lock_version < 0):
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
        if (len({item.operation_id for item in view.operations}) != len(view.operations)
                or len(set(view.enabled_operations)) != len(view.enabled_operations)
                or not set(view.enabled_operations).issubset(
                    {item.operation_id for item in view.operations}
                )):
            raise PluginInstallationMetadataError("PLUGIN_INSTALLATION_UNAVAILABLE")
