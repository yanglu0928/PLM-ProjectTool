"""Internal PLT-01 version commands; no public route is registered yet."""

from __future__ import annotations

import uuid
import hashlib
import json
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
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ActivateConfigurationVersion:
    configuration_id: uuid.UUID
    actor_id: uuid.UUID
    expected_lock_version: int
    version_no: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CreateConfiguration:
    config_key: str
    actor_id: uuid.UUID
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ConfigurationCommandResult:
    configuration_id: uuid.UUID
    version_id: uuid.UUID | None
    version_no: int | None
    lock_version: int


class ConfigurationRepositoryPort(Protocol):
    def add_configuration(self, uow: UnitOfWork, *, configuration_id: uuid.UUID, config_key: str, actor_id: uuid.UUID) -> bool: ...
    def lock(self, uow: UnitOfWork, configuration_id: uuid.UUID) -> ConfigurationSnapshot | None: ...
    def latest(self, uow: UnitOfWork, configuration_id: uuid.UUID) -> ConfigurationVersionSnapshot | None: ...
    def get_version(self, uow: UnitOfWork, configuration_id: uuid.UUID, version_no: int) -> ConfigurationVersionSnapshot | None: ...
    def add_version(self, uow: UnitOfWork, *, configuration_id: uuid.UUID, version_id: uuid.UUID, version_no: int, supersedes_version_id: uuid.UUID | None, schema_version: int, value_type: str, value: Any, fingerprint: bytes, actor_id: uuid.UUID) -> None: ...
    def update_root(self, uow: UnitOfWork, *, configuration_id: uuid.UUID, expected_lock_version: int, actor_id: uuid.UUID, active_version_id: uuid.UUID | None = None) -> bool: ...


class ConfigurationReceiptPort(Protocol):
    def reserve(self, uow: UnitOfWork, *, actor_id: uuid.UUID, operation: str, key_digest: bytes, request_fingerprint: bytes) -> ConfigurationCommandResult | None: ...
    def complete(self, uow: UnitOfWork, *, actor_id: uuid.UUID, operation: str, key_digest: bytes, result: ConfigurationCommandResult) -> None: ...


class ConfigurationAccessPort(Protocol):
    def require_deployment_write(self, uow: UnitOfWork, actor_id: uuid.UUID) -> None:
        """Verify authenticated Session, valid License and DeploymentAdmin."""


class ConfigurationAuditPort(Protocol):
    def append(self, uow: UnitOfWork, *, action: str, actor_id: uuid.UUID, configuration_id: uuid.UUID, version_id: uuid.UUID | None, trace_id: str) -> None:
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
        receipts: ConfigurationReceiptPort,
        policies: Mapping[str, ConfigurationValuePolicy],
    ) -> None:
        if any(item is None for item in (unit_of_work, repository, access, audit, receipts, policies)):
            raise ValueError("configuration command dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._access = access
        self._audit = audit
        self._receipts = receipts
        self._policies = dict(policies)

    def create_configuration(self, command: CreateConfiguration) -> ConfigurationCommandResult:
        if type(command.actor_id) is not uuid.UUID or command.actor_id.int == 0:
            raise ConfigurationCommandError("VALIDATION_FAILED")
        key_digest = _key_digest(command.idempotency_key)
        request_fingerprint = _payload_fingerprint({"config_key": command.config_key})
        trace_id = current_trace_id() or new_uuid7()
        with self._unit_of_work() as uow:
            self._require_access(uow, command.actor_id)
            replay = self._receipts.reserve(
                uow, actor_id=command.actor_id, operation="CREATE",
                key_digest=key_digest, request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            policy = self._policies.get(command.config_key)
            if policy is None or policy.config_key != command.config_key:
                raise ConfigurationCommandError("PLATFORM_SENSITIVE_VALUE_FORBIDDEN")
            configuration_id = uuid.UUID(new_uuid7())
            if not self._repository.add_configuration(
                uow, configuration_id=configuration_id,
                config_key=command.config_key, actor_id=command.actor_id,
            ):
                raise ConfigurationCommandError("CONFLICT_DUPLICATE")
            self._append_audit(
                uow, action="CONFIG_CREATED", actor_id=command.actor_id,
                configuration_id=configuration_id, version_id=None, trace_id=trace_id,
            )
            result = ConfigurationCommandResult(configuration_id, None, None, 0)
            self._receipts.complete(
                uow, actor_id=command.actor_id, operation="CREATE",
                key_digest=key_digest, result=result,
            )
            uow.commit()
            return result

    def create_version(self, command: CreateConfigurationVersion) -> ConfigurationCommandResult:
        _require_identity(command.configuration_id, command.actor_id)
        _require_lock_version(command.expected_lock_version)
        key_digest = _key_digest(command.idempotency_key)
        request_fingerprint = _payload_fingerprint({
            "configuration_id": str(command.configuration_id),
            "expected_lock_version": command.expected_lock_version,
            "schema_version": command.schema_version,
            "value": command.value,
        })
        trace_id = current_trace_id() or new_uuid7()
        with self._unit_of_work() as uow:
            self._require_access(uow, command.actor_id)
            replay = self._receipts.reserve(
                uow, actor_id=command.actor_id, operation="CREATE_VERSION",
                key_digest=key_digest, request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
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
            self._append_audit(
                uow, action="CONFIG_VERSION_CREATED", actor_id=command.actor_id,
                configuration_id=command.configuration_id, version_id=version_id,
                trace_id=trace_id,
            )
            result = ConfigurationCommandResult(
                command.configuration_id, version_id, version_no, root.lock_version + 1
            )
            self._receipts.complete(
                uow, actor_id=command.actor_id, operation="CREATE_VERSION",
                key_digest=key_digest, result=result,
            )
            uow.commit()
            return result

    def activate_version(self, command: ActivateConfigurationVersion) -> ConfigurationCommandResult:
        _require_identity(command.configuration_id, command.actor_id)
        _require_lock_version(command.expected_lock_version)
        if type(command.version_no) is not int or command.version_no < 1:
            raise ConfigurationCommandError("VALIDATION_FAILED")
        key_digest = _key_digest(command.idempotency_key)
        request_fingerprint = _payload_fingerprint({
            "configuration_id": str(command.configuration_id),
            "expected_lock_version": command.expected_lock_version,
            "version_no": command.version_no,
        })
        trace_id = current_trace_id() or new_uuid7()
        with self._unit_of_work() as uow:
            self._require_access(uow, command.actor_id)
            replay = self._receipts.reserve(
                uow, actor_id=command.actor_id, operation="ACTIVATE",
                key_digest=key_digest, request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
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
            self._append_audit(
                uow, action="CONFIG_VERSION_ACTIVATED", actor_id=command.actor_id,
                configuration_id=command.configuration_id, version_id=version.version_id,
                trace_id=trace_id,
            )
            result = ConfigurationCommandResult(
                command.configuration_id, version.version_id,
                version.version_no, root.lock_version + 1,
            )
            self._receipts.complete(
                uow, actor_id=command.actor_id, operation="ACTIVATE",
                key_digest=key_digest, result=result,
            )
            uow.commit()
            return result

    def _append_audit(
        self, uow: UnitOfWork, *, action: str, actor_id: uuid.UUID,
        configuration_id: uuid.UUID, version_id: uuid.UUID | None,
        trace_id: str,
    ) -> None:
        try:
            self._audit.append(
                uow, action=action, actor_id=actor_id,
                configuration_id=configuration_id, version_id=version_id,
                trace_id=trace_id,
            )
        except Exception:
            raise ConfigurationCommandError("SYSTEM_UNAVAILABLE") from None

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


def _key_digest(key: str) -> bytes:
    if (
        type(key) is not str or not 16 <= len(key) <= 128
        or any(not 32 <= ord(character) <= 126 for character in key)
    ):
        raise ConfigurationCommandError("VALIDATION_FAILED")
    return hashlib.sha256(key.encode("ascii")).digest()


def _payload_fingerprint(payload: dict[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ConfigurationCommandError("VALIDATION_FAILED") from None
    if len(encoded) > 4096:
        raise ConfigurationCommandError("VALIDATION_FAILED")
    return hashlib.sha256(encoded).digest()
