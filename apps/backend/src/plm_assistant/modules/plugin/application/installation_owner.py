"""Controlled PluginInstallation fact owner.

This application service records an installation only after an internal installation
adapter independently confirms the exact verified package is present on the host.
It does not copy package files, enable operations, or execute plugins.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork

_OS = frozenset({"windows-11", "windows-server-2025", "debian-13"})
_VERSION = re.compile(r"^[0-9]{1,3}(?:\.[0-9]{1,3}){1,3}$", re.ASCII)
_DEP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", re.ASCII)
_DEP_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+!_-]{0,63}$", re.ASCII)


class PluginInstallationOwnerError(RuntimeError):
    """Stable, non-sensitive rejection for an installation fact command."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RecordPluginInstallationCommand:
    plugin_installation_id: uuid.UUID
    plugin_package_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class InstallablePluginPackage:
    plugin_package_id: uuid.UUID
    plugin_id_normalized: str
    package_sha256: bytes = field(repr=False)
    manifest_snapshot: dict = field(repr=False)


@dataclass(frozen=True, slots=True)
class PluginInstallationEvidence:
    """Metadata returned by a trusted internal host adapter; contains no paths or bytes."""

    plugin_package_id: uuid.UUID
    installed_package_sha256: bytes = field(repr=False)
    installation_present: bool
    compatible: bool
    runtime_snapshot: dict = field(repr=False)


class PluginInstalledPackageEvidencePort(Protocol):
    def inspect_installed_package(
        self, package: InstallablePluginPackage,
    ) -> PluginInstallationEvidence | None: ...


@dataclass(frozen=True, slots=True)
class PluginInstallationIdentity:
    plugin_installation_id: uuid.UUID
    plugin_package_id: uuid.UUID
    plugin_id_normalized: str
    installed_by: uuid.UUID
    installation_state: str
    validated_runtime_snapshot: dict = field(repr=False)


class PluginInstallationRepositoryPort(Protocol):
    def lock_installation(self, transaction: object, *, installation_id: uuid.UUID) -> None: ...
    def find_installation(
        self, transaction: object, *, installation_id: uuid.UUID,
    ) -> PluginInstallationIdentity | None: ...
    def find_verified_package(
        self, transaction: object, *, package_id: uuid.UUID,
    ) -> InstallablePluginPackage | None: ...
    def authorize_owner_inserts(self, transaction: object) -> None: ...
    def create_installed(
        self, transaction: object, *, installation_id: uuid.UUID,
        package: InstallablePluginPackage, actor_id: uuid.UUID,
        runtime_snapshot: dict,
    ) -> PluginInstallationIdentity: ...
    def append_runtime_validation(
        self, transaction: object, *, installation_id: uuid.UUID,
        actor_id: uuid.UUID, runtime_snapshot: dict,
    ) -> None: ...


class PluginInstallationOwner:
    """Records one observed installation and compatibility fact atomically."""

    def __init__(
        self, *, unit_of_work: Callable[[], UnitOfWork],
        evidence: PluginInstalledPackageEvidencePort,
        repository: PluginInstallationRepositoryPort,
        audit: AuditService,
    ) -> None:
        if any(value is None for value in (unit_of_work, evidence, repository, audit)):
            raise ValueError("Plugin installation owner dependencies are required")
        self._uow = unit_of_work
        self._evidence = evidence
        self._repository = repository
        self._audit = audit

    def record(
        self, command: RecordPluginInstallationCommand, *,
        commit_guard: Callable[[object], None] | None = None,
    ) -> PluginInstallationIdentity:
        self._validate_command(command)
        if commit_guard is not None and not callable(commit_guard):
            raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_INVALID")
        try:
            with self._uow() as transaction:
                if commit_guard is not None:
                    commit_guard(transaction)
                self._repository.lock_installation(
                    transaction, installation_id=command.plugin_installation_id,
                )
                existing = self._repository.find_installation(
                    transaction, installation_id=command.plugin_installation_id,
                )
                if existing is not None:
                    if (existing.plugin_package_id != command.plugin_package_id
                            or existing.installed_by != command.actor_id):
                        raise PluginInstallationOwnerError(
                            "PLUGIN_INSTALLATION_ID_CONFLICT"
                        )
                    transaction.commit()
                    return existing

                package = self._repository.find_verified_package(
                    transaction, package_id=command.plugin_package_id,
                )
                if type(package) is not InstallablePluginPackage:
                    raise PluginInstallationOwnerError("PLUGIN_PACKAGE_NOT_INSTALLABLE")
                self._validate_package(package)
                observed = self._evidence.inspect_installed_package(package)
                if type(observed) is not PluginInstallationEvidence:
                    raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_EVIDENCE_UNAVAILABLE")
                snapshot = self._validate_evidence(package, observed)
                self._repository.authorize_owner_inserts(transaction)
                installation = self._repository.create_installed(
                    transaction,
                    installation_id=command.plugin_installation_id,
                    package=package,
                    actor_id=command.actor_id,
                    runtime_snapshot=snapshot,
                )
                self._repository.append_runtime_validation(
                    transaction, installation_id=command.plugin_installation_id,
                    actor_id=command.actor_id, runtime_snapshot=snapshot,
                )
                self._audit.append(
                    transaction,
                    AuditEventDraft(
                        trace_id=command.trace_id,
                        event_scope="DEPLOYMENT",
                        target_project_id=None,
                        actor_type="USER",
                        actor_id=command.actor_id,
                        original_actor_id=None,
                        actor_hint_digest=None,
                        action="PLUGIN_INSTALLATION_RECORD",
                        outcome="SUCCESS",
                        target_owner_module="plugin",
                        target_object_type="PLG-02",
                        target_object_id=command.plugin_installation_id,
                        after_state="INSTALLED",
                    ),
                )
                transaction.commit()
                return installation
        except PluginInstallationOwnerError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if type(code) is str and code.startswith("PLUGIN_"):
                raise PluginInstallationOwnerError(code) from None
            raise PluginInstallationOwnerError(
                "PLUGIN_INSTALLATION_STORE_UNAVAILABLE"
            ) from None

    @staticmethod
    def _validate_command(command: object) -> None:
        if (type(command) is not RecordPluginInstallationCommand
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.plugin_installation_id, command.plugin_package_id,
                    command.actor_id, command.trace_id,
                ))):
            raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_INVALID")

    @staticmethod
    def _validate_package(package: InstallablePluginPackage) -> None:
        if (type(package.plugin_package_id) is not uuid.UUID
                or package.plugin_package_id.int == 0
                or type(package.plugin_id_normalized) is not str
                or not 2 <= len(package.plugin_id_normalized) <= 128
                or package.plugin_id_normalized != package.plugin_id_normalized.lower()
                or type(package.package_sha256) is not bytes
                or len(package.package_sha256) != 32
                or type(package.manifest_snapshot) is not dict
                or package.manifest_snapshot.get("schema_version") != "plm.plugin.manifest.v1"):
            raise PluginInstallationOwnerError("PLUGIN_PACKAGE_NOT_INSTALLABLE")

    @staticmethod
    def _validate_evidence(
        package: InstallablePluginPackage, evidence: PluginInstallationEvidence,
    ) -> dict:
        if (type(evidence.plugin_package_id) is not uuid.UUID
                or evidence.plugin_package_id != package.plugin_package_id
                or type(evidence.installed_package_sha256) is not bytes
                or not __import__("hmac").compare_digest(
                    evidence.installed_package_sha256, package.package_sha256,
                )
                or evidence.installation_present is not True):
            raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_EVIDENCE_INVALID")
        if evidence.compatible is not True:
            raise PluginInstallationOwnerError("PLUGIN_RUNTIME_INCOMPATIBLE")
        snapshot = evidence.runtime_snapshot
        required = {
            "schema_version", "os", "architecture", "python_version",
            "dependency_versions",
        }
        if type(snapshot) is not dict or set(snapshot) != required:
            raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_EVIDENCE_INVALID")
        if (snapshot["schema_version"] != "1"
                or snapshot["os"] not in _OS
                or snapshot["architecture"] != "x86_64"
                or type(snapshot["python_version"]) is not str
                or not _VERSION.fullmatch(snapshot["python_version"])):
            raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_EVIDENCE_INVALID")
        dependencies = snapshot["dependency_versions"]
        if (type(dependencies) is not dict or len(dependencies) > 256
                or any(type(name) is not str or not _DEP_NAME.fullmatch(name)
                       or type(version) is not str or not _DEP_VERSION.fullmatch(version)
                       for name, version in dependencies.items())):
            raise PluginInstallationOwnerError("PLUGIN_INSTALLATION_EVIDENCE_INVALID")
        return {
            "schema_version": "1",
            "os": snapshot["os"],
            "architecture": snapshot["architecture"],
            "python_version": snapshot["python_version"],
            "dependency_versions": dict(sorted(dependencies.items())),
        }
