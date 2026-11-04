"""Atomic, auditable activation of declared Plugin operations."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.unit_of_work import UnitOfWork

@dataclass(frozen=True, slots=True)
class EnablePluginOperationsCommand:
    plugin_installation_id: uuid.UUID
    operation_ids: tuple[str, ...]
    expected_lock_version: int
    actor_id: uuid.UUID
    trace_id: uuid.UUID

@dataclass(frozen=True, slots=True)
class DisablePluginInstallationCommand:
    plugin_installation_id: uuid.UUID
    expected_lock_version: int
    actor_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PluginActivationContext:
    plugin_id_normalized: str
    target_installation_id: uuid.UUID
    target_package_id: uuid.UUID
    target_package_state: str
    target_state: str
    target_lock_version: int
    target_runtime_snapshot: dict = field(repr=False)
    latest_validation_state: str | None = None
    latest_runtime_snapshot: dict = field(default_factory=dict, repr=False)
    declared_operations: frozenset[str] = frozenset()
    installation_states: dict[uuid.UUID, str] = field(default_factory=dict, repr=False)
    installation_lock_versions: dict[uuid.UUID, int] = field(default_factory=dict, repr=False)
    package_ids: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict, repr=False)
    enabled_operations: dict[uuid.UUID, frozenset[str]] = field(default_factory=dict, repr=False)

@dataclass(frozen=True, slots=True)
class PluginOperationTransition:
    installation_id: uuid.UUID
    package_id: uuid.UUID
    operation_id: str
    transition: str
    before_state: str
    after_state: str

@dataclass(frozen=True, slots=True)
class PluginActivationResult:
    plugin_installation_id: uuid.UUID
    installation_state: str
    lock_version: int
    enabled_operations: tuple[str, ...]
    changed: bool

class PluginActivationOwnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

class PluginActivationRepositoryPort(Protocol):
    def identify_plugin(self, transaction: object, *, installation_id: uuid.UUID) -> str | None: ...
    def lock_plugin(self, transaction: object, *, plugin_id: str) -> None: ...
    def load_activation_context(self, transaction: object, *,
                               installation_id: uuid.UUID) -> PluginActivationContext | None: ...
    def authorize_owner_writes(self, transaction: object) -> None: ...
    def apply_activation(self, transaction: object, *, context: PluginActivationContext,
                         desired_operations: frozenset[str],
                         new_states: dict[uuid.UUID, str], actor_id: uuid.UUID,
                         changed_at: datetime) -> None: ...
    def append_operation_history(self, transaction: object, *,
                                 transition: PluginOperationTransition,
                                 actor_id: uuid.UUID, trace_id: uuid.UUID,
                                 audit_event_id: uuid.UUID) -> None: ...

class PluginActivationOwner:
    """Transfer an exact Manifest operation subset in one audited transaction."""
    def __init__(self, *, unit_of_work: Callable[[], UnitOfWork],
                 repository: PluginActivationRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, repository, audit)):
            raise ValueError("Plugin activation owner dependencies are required")
        self._uow, self._repository, self._audit = unit_of_work, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def enable(self, command: EnablePluginOperationsCommand, *,
               commit_guard: Callable[[object], None] | None = None) -> PluginActivationResult:
        self._validate_command(command)
        if ((commit_guard is not None and not callable(commit_guard))
                or (result_guard is not None and not callable(result_guard))):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_INVALID")
        try:
            with self._uow() as transaction:
                if commit_guard is not None:
                    commit_guard(transaction)
                plugin_id = self._repository.identify_plugin(
                    transaction, installation_id=command.plugin_installation_id)
                if plugin_id is None:
                    raise PluginActivationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
                self._repository.lock_plugin(transaction, plugin_id=plugin_id)
                context = self._repository.load_activation_context(
                    transaction, installation_id=command.plugin_installation_id)
                if context is None:
                    raise PluginActivationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
                self._validate_context(context, command)
                desired = frozenset(command.operation_ids)
                target_id = command.plugin_installation_id
                current_target = context.enabled_operations.get(target_id, frozenset())
                if context.target_state == "ENABLED" and current_target == desired:
                    transaction.commit()
                    return PluginActivationResult(
                        target_id, "ENABLED", context.target_lock_version,
                        tuple(sorted(desired)), False)
                if command.expected_lock_version != context.target_lock_version:
                    raise PluginActivationOwnerError("PLUGIN_LOCK_VERSION_CONFLICT")

                owners: dict[str, uuid.UUID] = {}
                for installation_id, operations in context.enabled_operations.items():
                    for operation_id in operations.intersection(desired):
                        if installation_id != target_id:
                            if operation_id in owners:
                                raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
                            owners[operation_id] = installation_id

                remaining: dict[uuid.UUID, frozenset[str]] = {}
                for installation_id, operations in context.enabled_operations.items():
                    next_ops = desired if installation_id == target_id else frozenset(operations - desired)
                    if next_ops != operations:
                        remaining[installation_id] = next_ops
                if target_id not in remaining:
                    remaining[target_id] = desired

                new_states = {target_id: "ENABLED"}
                for installation_id, next_ops in remaining.items():
                    if installation_id == target_id:
                        continue
                    if context.installation_states.get(installation_id) != "ENABLED":
                        raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
                    new_states[installation_id] = "ENABLED" if next_ops else "DISABLED"

                transitions: list[PluginOperationTransition] = []
                for operation_id in sorted(current_target - desired):
                    transitions.append(PluginOperationTransition(
                        target_id, context.target_package_id, operation_id,
                        "DISABLED", context.target_state, "ENABLED"))
                for operation_id in sorted(desired - current_target):
                    old_id = owners.get(operation_id)
                    if old_id is not None:
                        old_state = context.installation_states[old_id]
                        transitions.append(PluginOperationTransition(
                            old_id, context.package_ids[old_id], operation_id,
                            "DISABLED", old_state, new_states[old_id]))
                    transitions.append(PluginOperationTransition(
                        target_id, context.target_package_id, operation_id,
                        "ENABLED", context.target_state, "ENABLED"))

                changed_at = self._clock()
                if changed_at.tzinfo is None or changed_at.utcoffset() is None:
                    raise PluginActivationOwnerError("PLUGIN_ACTIVATION_INVALID")
                self._repository.authorize_owner_writes(transaction)
                self._repository.apply_activation(
                    transaction, context=context, desired_operations=desired,
                    new_states=new_states, actor_id=command.actor_id, changed_at=changed_at)
                for transition in transitions:
                    audit_id = self._audit.append(
                        transaction,
                        AuditEventDraft(
                            trace_id=command.trace_id, event_scope="DEPLOYMENT",
                            target_project_id=None, actor_type="USER",
                            actor_id=command.actor_id, original_actor_id=None,
                            actor_hint_digest=None,
                            action=("PLUGIN_OPERATION_ENABLE"
                                    if transition.transition == "ENABLED"
                                    else "PLUGIN_OPERATION_DISABLE"),
                            outcome="SUCCESS", target_owner_module="plugin",
                            target_object_type="PLG-02",
                            target_object_id=transition.installation_id,
                            reason_code="OPERATION_SET_CHANGED",
                            before_state=transition.before_state,
                            after_state=transition.after_state))
                    self._repository.append_operation_history(
                        transaction, transition=transition, actor_id=command.actor_id,
                        trace_id=command.trace_id, audit_event_id=audit_id)
                transaction.commit()
                return PluginActivationResult(
                    target_id, "ENABLED", context.target_lock_version + 1,
                    tuple(sorted(desired)), True)
        except PluginActivationOwnerError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if type(code) is str and code.startswith("PLUGIN_"):
                raise PluginActivationOwnerError(code) from None
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STORE_UNAVAILABLE") from None

    def disable(
        self, command: DisablePluginInstallationCommand, *,
        commit_guard: Callable[[object], None] | None = None,
        result_guard: Callable[[object, PluginActivationResult], None] | None = None,
    ) -> PluginActivationResult:
        """Disable every operation on one Installation as one audited transition."""
        if (type(command) is not DisablePluginInstallationCommand
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.plugin_installation_id, command.actor_id, command.trace_id))
                or type(command.expected_lock_version) is not int
                or command.expected_lock_version < 0):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_INVALID")
        if commit_guard is not None and not callable(commit_guard):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_INVALID")
        try:
            with self._uow() as transaction:
                if commit_guard is not None:
                    commit_guard(transaction)
                target_id = command.plugin_installation_id
                plugin_id = self._repository.identify_plugin(
                    transaction, installation_id=target_id)
                if plugin_id is None:
                    raise PluginActivationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
                self._repository.lock_plugin(transaction, plugin_id=plugin_id)
                context = self._repository.load_activation_context(
                    transaction, installation_id=target_id)
                if context is None:
                    raise PluginActivationOwnerError("PLUGIN_INSTALLATION_NOT_FOUND")
                self._validate_disable_context(context, command)
                if command.expected_lock_version != context.target_lock_version:
                    raise PluginActivationOwnerError("PLUGIN_LOCK_VERSION_CONFLICT")
                current = context.enabled_operations.get(target_id, frozenset())
                if context.target_state == "DISABLED":
                    result = PluginActivationResult(
                        target_id, "DISABLED", context.target_lock_version, (), False)
                    if result_guard is not None:
                        result_guard(transaction, result)
                    transaction.commit()
                    return result
                if not current:
                    raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
                changed_at = self._clock()
                if changed_at.tzinfo is None or changed_at.utcoffset() is None:
                    raise PluginActivationOwnerError("PLUGIN_ACTIVATION_INVALID")
                self._repository.authorize_owner_writes(transaction)
                self._repository.apply_activation(
                    transaction, context=context, desired_operations=frozenset(),
                    new_states={target_id: "DISABLED"}, actor_id=command.actor_id,
                    changed_at=changed_at)
                for operation_id in sorted(current):
                    transition = PluginOperationTransition(
                        target_id, context.target_package_id, operation_id,
                        "DISABLED", "ENABLED", "DISABLED")
                    audit_id = self._audit.append(
                        transaction,
                        AuditEventDraft(
                            trace_id=command.trace_id, event_scope="DEPLOYMENT",
                            target_project_id=None, actor_type="USER",
                            actor_id=command.actor_id, original_actor_id=None,
                            actor_hint_digest=None, action="PLUGIN_OPERATION_DISABLE",
                            outcome="SUCCESS", target_owner_module="plugin",
                            target_object_type="PLG-02",
                            target_object_id=target_id,
                            reason_code="ADMIN_DISABLED",
                            before_state="ENABLED", after_state="DISABLED"))
                    self._repository.append_operation_history(
                        transaction, transition=transition, actor_id=command.actor_id,
                        trace_id=command.trace_id, audit_event_id=audit_id)
                result = PluginActivationResult(
                    target_id, "DISABLED", context.target_lock_version + 1, (), True)
                if result_guard is not None:
                    result_guard(transaction, result)
                transaction.commit()
                return result
        except PluginActivationOwnerError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if type(code) is str and code.startswith("PLUGIN_"):
                raise PluginActivationOwnerError(code) from None
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STORE_UNAVAILABLE") from None

    @staticmethod
    def _validate_disable_context(
        context: PluginActivationContext, command: DisablePluginInstallationCommand,
    ) -> None:
        target_id = command.plugin_installation_id
        if (type(context) is not PluginActivationContext
                or context.target_installation_id != target_id
                or context.target_package_state != "VERIFIED"
                or context.target_state not in ("ENABLED", "DISABLED")
                or context.latest_validation_state != "COMPATIBLE"
                or context.latest_runtime_snapshot != context.target_runtime_snapshot
                or type(context.target_lock_version) is not int
                or context.target_lock_version < 0
                or context.installation_states.get(target_id) != context.target_state
                or context.installation_lock_versions.get(target_id) != context.target_lock_version):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_NOT_ALLOWED")
        current = context.enabled_operations.get(target_id, frozenset())
        if (not current and context.target_state == "ENABLED"
                or current and context.target_state != "ENABLED"):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
        if not current.issubset(context.declared_operations):
            raise PluginActivationOwnerError("PLUGIN_OPERATION_NOT_DECLARED")
        for installation_id, operations in context.enabled_operations.items():
            if operations and context.installation_states.get(installation_id) != "ENABLED":
                raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
        if any(type(v) is not int or v < 0
               for v in context.installation_lock_versions.values()):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")

    @staticmethod
    def _validate_command(command: object) -> None:
        if (type(command) is not EnablePluginOperationsCommand
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.plugin_installation_id, command.actor_id, command.trace_id))
                or type(command.expected_lock_version) is not int
                or command.expected_lock_version < 0
                or type(command.operation_ids) is not tuple
                or not 1 <= len(command.operation_ids) <= 256
                or any(type(item) is not str or not 1 <= len(item) <= 255
                       or item != item.strip()
                       or any(ord(char) < 32 or ord(char) == 127 for char in item)
                       for item in command.operation_ids)
                or len(set(command.operation_ids)) != len(command.operation_ids)):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_INVALID")

    @staticmethod
    def _validate_context(context: PluginActivationContext,
                          command: EnablePluginOperationsCommand) -> None:
        target_id = command.plugin_installation_id
        if (type(context) is not PluginActivationContext
                or context.target_installation_id != target_id
                or context.target_package_state != "VERIFIED"
                or context.target_state not in ("INSTALLED", "DISABLED", "ENABLED")
                or context.latest_validation_state != "COMPATIBLE"
                or context.latest_runtime_snapshot != context.target_runtime_snapshot
                or context.target_lock_version < 0
                or context.installation_states.get(target_id) != context.target_state
                or context.installation_lock_versions.get(target_id) != context.target_lock_version
                or (context.target_state != "ENABLED"
                    and context.enabled_operations.get(target_id, frozenset()))):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_NOT_ALLOWED")
        if not set(command.operation_ids).issubset(context.declared_operations):
            raise PluginActivationOwnerError("PLUGIN_OPERATION_NOT_DECLARED")
        for installation_id, operations in context.enabled_operations.items():
            if operations and context.installation_states.get(installation_id) != "ENABLED":
                raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
        if any(type(v) is not int or v < 0 for v in context.installation_lock_versions.values()):
            raise PluginActivationOwnerError("PLUGIN_ACTIVATION_STATE_CONFLICT")
