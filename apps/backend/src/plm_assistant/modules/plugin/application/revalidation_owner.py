"""Revalidate a Plugin installation and fail closed on incompatibility."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork
from plm_assistant.modules.plugin.application.installation_owner import (
    InstallablePluginPackage, PluginInstallationEvidence,
    PluginInstalledPackageEvidencePort, PluginInstallationOwner,
)

@dataclass(frozen=True, slots=True)
class RevalidatePluginInstallationCommand:
    plugin_installation_id: uuid.UUID
    expected_lock_version: int
    actor_id: uuid.UUID
    trace_id: uuid.UUID

@dataclass(frozen=True, slots=True)
class PluginRuntimeRevalidationContext:
    plugin_id_normalized: str
    plugin_installation_id: uuid.UUID
    package: InstallablePluginPackage = field(repr=False)
    package_state: str
    installation_state: str
    lock_version: int
    current_runtime_snapshot: dict = field(repr=False)
    latest_validation_state: str
    latest_runtime_snapshot: dict = field(repr=False)
    enabled_operations: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class PluginRuntimeRevalidationResult:
    plugin_installation_id: uuid.UUID
    installation_state: str
    compatibility_state: str
    lock_version: int
    disabled_operations: tuple[str, ...]

class PluginRuntimeRevalidationOwnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

class PluginRuntimeRevalidationRepositoryPort(Protocol):
    def identify_plugin(self, transaction: object, *, installation_id: uuid.UUID) -> str | None: ...
    def lock_plugin(self, transaction: object, *, plugin_id: str) -> None: ...
    def load_context(self, transaction: object, *, installation_id: uuid.UUID) -> PluginRuntimeRevalidationContext | None: ...
    def apply_revalidation(self, transaction: object, *, context: PluginRuntimeRevalidationContext,
                           compatibility_state: str, runtime_snapshot: dict,
                           installation_state: str, actor_id: uuid.UUID,
                           changed_at: datetime) -> None: ...
    def append_disabled_operation_history(self, transaction: object, *,
        installation_id: uuid.UUID, package_id: uuid.UUID, plugin_id: str,
        operation_id: str, actor_id: uuid.UUID, trace_id: uuid.UUID,
        audit_event_id: uuid.UUID) -> None: ...

class PluginRuntimeRevalidationOwner:
    def __init__(self, *, unit_of_work: Callable[[], UnitOfWork],
                 evidence: PluginInstalledPackageEvidencePort,
                 repository: PluginRuntimeRevalidationRepositoryPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, evidence, repository, audit)):
            raise ValueError("Plugin runtime revalidation dependencies are required")
        self._uow, self._evidence, self._repository, self._audit = unit_of_work, evidence, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revalidate(self, command: RevalidatePluginInstallationCommand, *,
                   commit_guard: Callable[[object], None] | None = None) -> PluginRuntimeRevalidationResult:
        self._validate_command(command)
        if commit_guard is not None and not callable(commit_guard):
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_INVALID")
        try:
            with self._uow() as transaction:
                if commit_guard is not None:
                    commit_guard(transaction)
                plugin_id = self._repository.identify_plugin(
                    transaction, installation_id=command.plugin_installation_id)
                if plugin_id is None:
                    raise PluginRuntimeRevalidationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
                self._repository.lock_plugin(transaction, plugin_id=plugin_id)
                context = self._repository.load_context(
                    transaction, installation_id=command.plugin_installation_id)
                if context is None:
                    raise PluginRuntimeRevalidationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
                self._validate_context(context, command)
                if command.expected_lock_version != context.lock_version:
                    raise PluginRuntimeRevalidationOwnerError("PLUGIN_LOCK_VERSION_CONFLICT")
                observed = self._evidence.inspect_installed_package(context.package)
                if type(observed) is not PluginInstallationEvidence:
                    raise PluginRuntimeRevalidationOwnerError("PLUGIN_INSTALLATION_EVIDENCE_UNAVAILABLE")
                try:
                    snapshot = PluginInstallationOwner._validate_evidence(
                        context.package, observed, require_compatible=False)
                except Exception as exc:
                    code = getattr(exc, "code", None)
                    if type(code) is str and code.startswith("PLUGIN_"):
                        raise PluginRuntimeRevalidationOwnerError(code) from None
                    raise
                compatibility = "COMPATIBLE" if observed.compatible else "INCOMPATIBLE"
                disabled = tuple(context.enabled_operations) if compatibility == "INCOMPATIBLE" else ()
                next_state = ("INCOMPATIBLE" if compatibility == "INCOMPATIBLE"
                              else ("DISABLED" if context.installation_state == "INCOMPATIBLE"
                                    else context.installation_state))
                changed_at = self._clock()
                if changed_at.tzinfo is None or changed_at.utcoffset() is None:
                    raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_INVALID")
                self._repository.apply_revalidation(
                    transaction, context=context, compatibility_state=compatibility,
                    runtime_snapshot=snapshot, installation_state=next_state,
                    actor_id=command.actor_id, changed_at=changed_at)
                self._audit.append(
                    transaction, AuditEventDraft(
                        trace_id=command.trace_id, event_scope="DEPLOYMENT",
                        target_project_id=None, actor_type="USER", actor_id=command.actor_id,
                        original_actor_id=None, actor_hint_digest=None,
                        action="PLUGIN_RUNTIME_REVALIDATE", outcome="SUCCESS",
                        target_owner_module="plugin", target_object_type="PLG-02",
                        target_object_id=context.plugin_installation_id,
                        reason_code=("RUNTIME_COMPATIBLE" if compatibility == "COMPATIBLE"
                                     else "RUNTIME_INCOMPATIBLE"),
                        before_state=context.installation_state, after_state=next_state))
                for operation_id in disabled:
                    audit_id = self._audit.append(
                        transaction, AuditEventDraft(
                            trace_id=command.trace_id, event_scope="DEPLOYMENT",
                            target_project_id=None, actor_type="USER", actor_id=command.actor_id,
                            original_actor_id=None, actor_hint_digest=None,
                            action="PLUGIN_OPERATION_DISABLE", outcome="SUCCESS",
                            target_owner_module="plugin", target_object_type="PLG-02",
                            target_object_id=context.plugin_installation_id,
                            reason_code="RUNTIME_INCOMPATIBLE", before_state="ENABLED",
                            after_state="INCOMPATIBLE"))
                    self._repository.append_disabled_operation_history(
                        transaction, installation_id=context.plugin_installation_id,
                        package_id=context.package.plugin_package_id, plugin_id=plugin_id,
                        operation_id=operation_id, actor_id=command.actor_id,
                        trace_id=command.trace_id, audit_event_id=audit_id)
                transaction.commit()
                return PluginRuntimeRevalidationResult(
                    context.plugin_installation_id, next_state, compatibility,
                    context.lock_version + 1, tuple(sorted(disabled)))
        except PluginRuntimeRevalidationOwnerError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if type(code) is str and code.startswith("PLUGIN_"):
                raise PluginRuntimeRevalidationOwnerError(code) from None
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_STORE_UNAVAILABLE") from None

    @staticmethod
    def _validate_command(command: object) -> None:
        if (type(command) is not RevalidatePluginInstallationCommand
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.plugin_installation_id, command.actor_id, command.trace_id))
                or type(command.expected_lock_version) is not int
                or command.expected_lock_version < 0):
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_INVALID")

    @staticmethod
    def _validate_context(context: PluginRuntimeRevalidationContext,
                          command: RevalidatePluginInstallationCommand) -> None:
        if (type(context) is not PluginRuntimeRevalidationContext
                or context.plugin_installation_id != command.plugin_installation_id
                or type(context.package) is not InstallablePluginPackage
                or context.package.plugin_package_id.int == 0
                or context.package_state != "VERIFIED"
                or context.installation_state not in ("INSTALLED", "ENABLED", "DISABLED", "INCOMPATIBLE")
                or context.latest_validation_state not in ("COMPATIBLE", "INCOMPATIBLE")
                or context.latest_runtime_snapshot != context.current_runtime_snapshot
                or type(context.lock_version) is not int or context.lock_version < 0
                or (context.installation_state == "ENABLED" and not context.enabled_operations)
                or (context.installation_state != "ENABLED" and context.enabled_operations)
                or any(type(op) is not str or not op for op in context.enabled_operations)):
            raise PluginRuntimeRevalidationOwnerError("PLUGIN_REVALIDATION_NOT_ALLOWED")
