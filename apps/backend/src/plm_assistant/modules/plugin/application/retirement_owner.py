"""Retire an installed Plugin as an auditable terminal state."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class RetirePluginInstallationCommand:
    plugin_installation_id: uuid.UUID
    expected_lock_version: int
    actor_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PluginInstallationRetirementContext:
    plugin_id_normalized: str
    plugin_installation_id: uuid.UUID
    plugin_package_id: uuid.UUID
    installation_state: str
    lock_version: int
    enabled_operations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PluginInstallationRetirementResult:
    plugin_installation_id: uuid.UUID
    installation_state: str
    lock_version: int
    disabled_operations: tuple[str, ...]


class PluginInstallationRetirementOwnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PluginInstallationRetirementRepositoryPort(Protocol):
    def identify_plugin(self, transaction: object, *, installation_id: uuid.UUID) -> str | None: ...
    def lock_plugin(self, transaction: object, *, plugin_id: str) -> None: ...
    def load_context(self, transaction: object, *,
                     installation_id: uuid.UUID) -> PluginInstallationRetirementContext | None: ...
    def authorize_owner_writes(self, transaction: object) -> None: ...
    def apply_retirement(self, transaction: object, *,
                         context: PluginInstallationRetirementContext,
                         actor_id: uuid.UUID, changed_at: datetime) -> None: ...
    def append_disabled_operation_history(self, transaction: object, *,
        installation_id: uuid.UUID, package_id: uuid.UUID, plugin_id: str,
        operation_id: str, actor_id: uuid.UUID, trace_id: uuid.UUID,
        audit_event_id: uuid.UUID) -> None: ...


class PluginInstallationRetirementOwner:
    def __init__(self, *, unit_of_work: Callable[[], UnitOfWork],
                 repository: PluginInstallationRetirementRepositoryPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if unit_of_work is None or repository is None or audit is None:
            raise ValueError("Plugin installation retirement dependencies are required")
        self._uow = unit_of_work
        self._repository = repository
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def retire(self, command: RetirePluginInstallationCommand, *,
               commit_guard: Callable[[object], None] | None = None
               ) -> PluginInstallationRetirementResult:
        self._validate_command(command)
        if commit_guard is not None and not callable(commit_guard):
            raise PluginInstallationRetirementOwnerError("PLUGIN_RETIREMENT_INVALID")
        try:
            with self._uow() as transaction:
                if commit_guard is not None:
                    commit_guard(transaction)
                plugin_id = self._repository.identify_plugin(
                    transaction, installation_id=command.plugin_installation_id)
                if plugin_id is None:
                    raise PluginInstallationRetirementOwnerError(
                        "PLUGIN_INSTALLATION_NOT_FOUND")
                self._repository.lock_plugin(transaction, plugin_id=plugin_id)
                context = self._repository.load_context(
                    transaction, installation_id=command.plugin_installation_id)
                if context is None:
                    raise PluginInstallationRetirementOwnerError(
                        "PLUGIN_INSTALLATION_NOT_FOUND")
                self._validate_context(context, command)
                if command.expected_lock_version != context.lock_version:
                    raise PluginInstallationRetirementOwnerError(
                        "PLUGIN_LOCK_VERSION_CONFLICT")
                changed_at = self._clock()
                if changed_at.tzinfo is None or changed_at.utcoffset() is None:
                    raise PluginInstallationRetirementOwnerError(
                        "PLUGIN_RETIREMENT_INVALID")

                self._repository.authorize_owner_writes(transaction)
                disabled = tuple(sorted(context.enabled_operations))
                for operation_id in disabled:
                    audit_id = self._audit.append(
                        transaction, AuditEventDraft(
                            trace_id=command.trace_id, event_scope="DEPLOYMENT",
                            target_project_id=None, actor_type="USER",
                            actor_id=command.actor_id, original_actor_id=None,
                            actor_hint_digest=None, action="PLUGIN_OPERATION_DISABLE",
                            outcome="SUCCESS", target_owner_module="plugin",
                            target_object_type="PLG-02",
                            target_object_id=context.plugin_installation_id,
                            reason_code="INSTALLATION_RETIRED",
                            before_state="ENABLED", after_state="RETIRED"))
                    self._repository.append_disabled_operation_history(
                        transaction, installation_id=context.plugin_installation_id,
                        package_id=context.plugin_package_id, plugin_id=plugin_id,
                        operation_id=operation_id, actor_id=command.actor_id,
                        trace_id=command.trace_id, audit_event_id=audit_id)
                self._audit.append(
                    transaction, AuditEventDraft(
                        trace_id=command.trace_id, event_scope="DEPLOYMENT",
                        target_project_id=None, actor_type="USER",
                        actor_id=command.actor_id, original_actor_id=None,
                        actor_hint_digest=None, action="PLUGIN_INSTALLATION_RETIRE",
                        outcome="SUCCESS", target_owner_module="plugin",
                        target_object_type="PLG-02",
                        target_object_id=context.plugin_installation_id,
                        reason_code="INSTALLATION_RETIRED",
                        before_state=context.installation_state, after_state="RETIRED"))
                self._repository.apply_retirement(
                    transaction, context=context, actor_id=command.actor_id,
                    changed_at=changed_at)
                transaction.commit()
                return PluginInstallationRetirementResult(
                    context.plugin_installation_id, "RETIRED",
                    context.lock_version + 1, disabled)
        except PluginInstallationRetirementOwnerError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if type(code) is str and code.startswith("PLUGIN_"):
                raise PluginInstallationRetirementOwnerError(code) from None
            raise PluginInstallationRetirementOwnerError(
                "PLUGIN_RETIREMENT_STORE_UNAVAILABLE") from None

    @staticmethod
    def _validate_command(command: object) -> None:
        if (type(command) is not RetirePluginInstallationCommand
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.plugin_installation_id, command.actor_id, command.trace_id))
                or type(command.expected_lock_version) is not int
                or command.expected_lock_version < 0):
            raise PluginInstallationRetirementOwnerError("PLUGIN_RETIREMENT_INVALID")

    @staticmethod
    def _validate_context(context: PluginInstallationRetirementContext,
                          command: RetirePluginInstallationCommand) -> None:
        states = ("INSTALLED", "ENABLED", "DISABLED", "INCOMPATIBLE")
        if type(context) is not PluginInstallationRetirementContext:
            raise PluginInstallationRetirementOwnerError(
                "PLUGIN_RETIREMENT_NOT_ALLOWED")
        valid_operations = (
            type(context.enabled_operations) is tuple
            and all(type(value) is str and bool(value)
                    for value in context.enabled_operations)
            and len(set(context.enabled_operations)) == len(context.enabled_operations)
        )
        if (context.plugin_installation_id != command.plugin_installation_id
                or type(context.plugin_id_normalized) is not str
                or not context.plugin_id_normalized
                or type(context.plugin_package_id) is not uuid.UUID
                or context.plugin_package_id.int == 0
                or context.installation_state not in states
                or type(context.lock_version) is not int
                or context.lock_version < 0
                or not valid_operations
                or (context.installation_state == "ENABLED"
                    and not context.enabled_operations)
                or (context.installation_state != "ENABLED"
                    and context.enabled_operations)):
            raise PluginInstallationRetirementOwnerError(
                "PLUGIN_RETIREMENT_NOT_ALLOWED")
