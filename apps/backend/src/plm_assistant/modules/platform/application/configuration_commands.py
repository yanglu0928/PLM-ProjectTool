"""Internal PLT-01 version commands; no public route is registered yet."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from plm_assistant.modules.platform.application.trace_context import (
    current_trace_id,
    new_uuid7,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork
from plm_assistant.modules.platform.domain.configuration import (
    ConfigurationValueError,
    ConfigurationValuePolicy,
)


class ConfigurationCommandError(ApplicationError):
    """A fixed public-safe command failure, carrying a stable error code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    configuration_id: uuid.UUID
    config_key: str
    lock_version: int
    active_version_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class ConfigurationVersionSnapshot:
    version_id: uuid.UUID
    version_no: int


@dataclass(frozen=True, slots=True)
class CreateConfigurationVersion:
    configuration_id: uuid.UUID
    actor_id: uuid.UUID
    expected_lock_version: int
    schema_version: int
    value: Any = field(repr=False)


@dataclass(frozen=True, slots=True)
class ActivateConfigurationVersion:
    configuration_id: uuid.UUID
    actor_id: uuid.UUID
    expected_lock_version: int
    version_no: int


@dataclass(frozen=True, slots=True)
class ConfigurationCommandResult:
    configuration_id: uuid.UUID
    version_id: uuid.UUID
    version_no: int
    lock_version: int


class ConfigurationRepositoryPort(Protocol):
    def lock(self, uow: UnitOfWork, configuration_id: uuid.UUID) -> ConfigurationSnapshot | None: ...
    def latest(self, uow: UnitOfWork, configuration_id: uuid.UUID) -> ConfigurationVersionSnapshot | None: ...
    def get_version(self, uow: UnitOfWork, configuration_id: uuid.UUID, version_no: int) -> ConfigurationVersionSnapshot | None: ...
    def add_version(self, uow: UnitOfWork, *, configuration_id: uuid.UUID, version_id: uuid.UUID, version_no: int, supersedes_version_id: uuid.UUID | None, schema_version: int, value_type: str, value: Any, fingerprint: bytes, actor_id: uuid.UUID) -> None: ...
    def update_root(self, uow: UnitOfWork, *, configuration_id: uuid.UUID, expected_lock_version: int, actor_id: uuid.UUID, active_version_id: uuid.UUID | None = None) -> bool: ...


class ConfigurationAccessPort(Protocol):
    def require_deployment_write(self, uow: UnitOfWork, actor_id: uuid.UUID) -> None:
        """Verify authenticated Session, valid License and DeploymentAdmin."""


class ConfigurationAuditPort(Protocol):
    def append(self, uow: UnitOfWork, *, action: str, actor_id: uuid.UUID, configuration_id: uuid.UUID, version_id: uuid.UUID, trace_id: str) -> None:
        """Append a safe Audit event in the same database transaction."""


class ConfigurationCommandService:
    """Fail closed if policy, authorization or same-transaction Audit is absent."""

    def __init__(
        self,
        *,
        unit_of_work: Callable[[], UnitOfWork],
        repository: ConfigurationRepositoryPort,
        access: ConfigurationAccessPort,
        audit: ConfigurationAuditPort,
        policies: Mapping[str, ConfigurationValuePolicy],
    ) -> None:
        if any(item is None for item in (unit_of_work, repository, access, audit, policies)):
            raise ValueError("configuration command dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._access = access
        self._audit = audit
        self._policies = dict(policies)

    def create_version(self, command: CreateConfigurationVersion) -> ConfigurationCommandResult:
        _require_identity(command.configuration_id, command.actor_id)
        _require_lock_version(command.expected_lock_version)
        trace_id = current_trace_id() or new_uuid7()
        with self._unit_of_work() as uow:
            self._require_access(uow, command.actor_id)
            root = self._repository.lock(uow, command.configuration_id)
            if root is None:
                raise ConfigurationCommandError("RESOURCE_NOT_FOUND")
            if root.lock_version != command.expected_lock_version:
                raise ConfigurationCommandError("CONFLICT_VERSION")
            policy = self._policies.get(root.config_key)
            if policy is None:
                raise ConfigurationCommandError("PLATFORM_SENSITIVE_VALUE_FORBIDDEN")
            try:
                fingerprint = policy.fingerprint(
                    schema_version=command.schema_version, value=command.value
                )
            except ConfigurationValueError:
                raise ConfigurationCommandError("PLATFORM_SENSITIVE_VALUE_FORBIDDEN") from None
            latest = self._repository.latest(uow, command.configuration_id)
            version_no = 1 if latest is None else latest.version_no + 1
            if version_no > 2_147_483_647:
                raise ConfigurationCommandError("CONFLICT_STATE")
            version_id = uuid.UUID(new_uuid7())
            self._repository.add_version(
                uow,
                configuration_id=command.configuration_id,
                version_id=version_id,
                version_no=version_no,
                supersedes_version_id=None if latest is None else latest.version_id,
                schema_version=command.schema_version,
                value_type=policy.value_type.value,
                value=command.value,
                fingerprint=fingerprint,
                actor_id=command.actor_id,
            )
            if not self._repository.update_root(
                uow,
                configuration_id=command.configuration_id,
                expected_lock_version=root.lock_version,
                actor_id=command.actor_id,
            ):
                raise ConfigurationCommandError("CONFLICT_VERSION")
            try:
                self._audit.append(
                    uow, action="CONFIG_VERSION_CREATED", actor_id=command.actor_id,
                    configuration_id=command.configuration_id, version_id=version_id,
                    trace_id=trace_id,
                )
            except Exception:
                raise ConfigurationCommandError("SYSTEM_UNAVAILABLE") from None
            uow.commit()
            return ConfigurationCommandResult(
                command.configuration_id, version_id, version_no, root.lock_version + 1
            )

    def activate_version(self, command: ActivateConfigurationVersion) -> ConfigurationCommandResult:
        _require_identity(command.configuration_id, command.actor_id)
        _require_lock_version(command.expected_lock_version)
        if type(command.version_no) is not int or command.version_no < 1:
            raise ConfigurationCommandError("VALIDATION_FAILED")
        trace_id = current_trace_id() or new_uuid7()
        with self._unit_of_work() as uow:
            self._require_access(uow, command.actor_id)
            root = self._repository.lock(uow, command.configuration_id)
            if root is None:
                raise ConfigurationCommandError("RESOURCE_NOT_FOUND")
            if root.lock_version != command.expected_lock_version:
                raise ConfigurationCommandError("CONFLICT_VERSION")
            version = self._repository.get_version(
                uow, command.configuration_id, command.version_no
            )
            if version is None:
                raise ConfigurationCommandError("RESOURCE_NOT_FOUND")
            if root.active_version_id == version.version_id:
                raise ConfigurationCommandError("CONFLICT_STATE")
            if not self._repository.update_root(
                uow, configuration_id=command.configuration_id,
                expected_lock_version=root.lock_version, actor_id=command.actor_id,
                active_version_id=version.version_id,
            ):
                raise ConfigurationCommandError("CONFLICT_VERSION")
            try:
                self._audit.append(
                    uow, action="CONFIG_VERSION_ACTIVATED", actor_id=command.actor_id,
                    configuration_id=command.configuration_id, version_id=version.version_id,
                    trace_id=trace_id,
                )
            except Exception:
                raise ConfigurationCommandError("SYSTEM_UNAVAILABLE") from None
            uow.commit()
            return ConfigurationCommandResult(
                command.configuration_id, version.version_id,
                version.version_no, root.lock_version + 1,
            )

    def _require_access(self, uow: UnitOfWork, actor_id: uuid.UUID) -> None:
        try:
            self._access.require_deployment_write(uow, actor_id)
        except ConfigurationCommandError:
            raise
        except Exception:
            raise ConfigurationCommandError("SYSTEM_UNAVAILABLE") from None


def _require_identity(configuration_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    if any(type(value) is not uuid.UUID or value.int == 0 for value in (configuration_id, actor_id)):
        raise ConfigurationCommandError("VALIDATION_FAILED")


def _require_lock_version(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ConfigurationCommandError("CONFLICT_VERSION_REQUIRED")
