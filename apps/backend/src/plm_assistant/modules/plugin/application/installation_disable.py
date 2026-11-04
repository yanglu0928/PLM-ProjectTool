"""Authorized, idempotent HTTP command orchestration for PluginInstallation disable."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.plugin.application.activation_owner import (
    DisablePluginInstallationCommand, PluginActivationOwner,
    PluginActivationOwnerError, PluginActivationResult,
)


class PluginInstallationDisableError(RuntimeError):
    def __init__(self, code: str) -> None:
        allowed = {
            "VALIDATION_FAILED", "AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND",
            "CONFLICT_VERSION", "CONFLICT_STATE", "CONFLICT_IDEMPOTENCY",
            "LICENSE_OPERATION_DENIED", "PLUGIN_DISABLE_UNAVAILABLE",
        }
        self.code = code if code in allowed else "PLUGIN_DISABLE_UNAVAILABLE"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class PluginInstallationDisableResult:
    result_id: uuid.UUID
    plugin_installation_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    expected_lock_version: int
    result_lock_version: int
    installation_state: str
    changed: bool
    created_at: datetime


class PluginDisableAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class PluginDisableReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...
    def lookup_result(self, transaction: object, *,
                      scope: IdempotencyScope) -> IdempotencyResult | None: ...


class PluginDisableResultRepositoryPort(Protocol):
    def record(self, transaction: object, *,
               command: DisablePluginInstallationCommand,
               result: PluginActivationResult) -> PluginInstallationDisableResult: ...
    def get(self, transaction: object, *,
            result_id: uuid.UUID) -> PluginInstallationDisableResult | None: ...


class PluginInstallationDisableService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: PluginDisableAccessPort, owner: PluginActivationOwner,
        receipts: PluginDisableReceiptPort,
        results: PluginDisableResultRepositoryPort, license_guard: object,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(item is None for item in (
            unit_of_work, access, owner, receipts, results, license_guard,
        )):
            raise ValueError("Plugin disable command dependencies are required")
        self._uow, self._access, self._owner = unit_of_work, access, owner
        self._receipts, self._results, self._guard = receipts, results, license_guard
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def disable(
        self, command: DisablePluginInstallationCommand, *,
        session_token: bytes, csrf_token: bytes, idempotency_key: str,
    ) -> PluginInstallationDisableResult:
        self._validate(command, session_token, csrf_token)
        try:
            validate_idempotency_key(idempotency_key)
            scope = IdempotencyScope.from_key(
                actor_id=command.actor_id, project_id=None,
                operation="V1_PLUGIN_DISABLE", key=idempotency_key,
            )
            fingerprint = canonical_payload_fingerprint({
                "plugin_installation_id": str(command.plugin_installation_id),
                "expected_lock_version": command.expected_lock_version,
                "request_schema": 1,
            })
        except IdempotencyError as exc:
            raise PluginInstallationDisableError(exc.code) from None
        snapshot: PluginInstallationDisableResult | None = None

        def authorize_and_reserve(transaction: object) -> None:
            nonlocal snapshot
            self._require_license(command.trace_id)
            self._require_admin(
                transaction, command, session_token=session_token,
                csrf_token=csrf_token,
            )
            try:
                replay = self._receipts.reserve(
                    transaction, scope=scope, request_fingerprint=fingerprint,
                )
            except IdempotencyError as exc:
                code = ("PLUGIN_CONFLICT_IDEMPOTENCY"
                        if exc.code == "CONFLICT_IDEMPOTENCY"
                        else "PLUGIN_DISABLE_UNAVAILABLE")
                raise PluginActivationOwnerError(code) from None
            if replay is not None:
                if (type(replay) is not IdempotencyResult
                        or replay.ref_type != "V1_PLUGIN_DISABLE"
                        or replay.status_code != 200):
                    raise PluginActivationOwnerError("PLUGIN_DISABLE_UNAVAILABLE")
                raise PluginActivationOwnerError("PLUGIN_DISABLE_REPLAY")

        def store_result(
            transaction: object, result: PluginActivationResult,
        ) -> None:
            nonlocal snapshot
            self._require_license(command.trace_id)
            try:
                snapshot = self._results.record(
                    transaction, command=command, result=result,
                )
                self._receipts.complete(
                    transaction, scope=scope,
                    result=IdempotencyResult("V1_PLUGIN_DISABLE", snapshot.result_id, 200),
                )
            except (IdempotencyError, PluginInstallationDisableError):
                raise
            except Exception:
                raise PluginActivationOwnerError("PLUGIN_DISABLE_UNAVAILABLE") from None

        try:
            result = self._owner.disable(
                command, commit_guard=authorize_and_reserve,
                result_guard=store_result,
            )
            if (type(result) is not PluginActivationResult or snapshot is None
                    or snapshot.plugin_installation_id != command.plugin_installation_id
                    or snapshot.result_lock_version != result.lock_version
                    or snapshot.changed != result.changed):
                raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
            return snapshot
        except PluginActivationOwnerError as exc:
            if exc.code == "PLUGIN_DISABLE_REPLAY":
                return self._replay(
                    command, scope=scope, session_token=session_token,
                    csrf_token=csrf_token,
                )
            raise PluginInstallationDisableError(self._map_owner_error(exc.code)) from None
        except RuntimeLicenseError:
            raise PluginInstallationDisableError("LICENSE_OPERATION_DENIED") from None
        except PluginInstallationDisableError:
            raise
        except Exception:
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE") from None

    def _replay(
        self, command: DisablePluginInstallationCommand, *,
        scope: IdempotencyScope, session_token: bytes, csrf_token: bytes,
    ) -> PluginInstallationDisableResult:
        try:
            self._require_license(command.trace_id)
            with self._uow() as transaction:
                self._require_admin(
                    transaction, command, session_token=session_token,
                    csrf_token=csrf_token,
                )
                receipt = self._receipts.lookup_result(transaction, scope=scope)
                if (type(receipt) is not IdempotencyResult
                        or receipt.ref_type != "V1_PLUGIN_DISABLE"
                        or receipt.status_code != 200):
                    raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
                result = self._results.get(transaction, result_id=receipt.ref_id)
                if (type(result) is not PluginInstallationDisableResult
                        or result.result_id != receipt.ref_id
                        or result.plugin_installation_id != command.plugin_installation_id
                        or result.actor_id != command.actor_id
                        or result.expected_lock_version != command.expected_lock_version):
                    raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE")
                return result
        except PluginInstallationDisableError:
            raise
        except RuntimeLicenseError:
            raise PluginInstallationDisableError("LICENSE_OPERATION_DENIED") from None
        except PluginActivationOwnerError as exc:
            raise PluginInstallationDisableError(self._map_owner_error(exc.code)) from None
        except Exception:
            raise PluginInstallationDisableError("PLUGIN_DISABLE_UNAVAILABLE") from None

    def _require_admin(
        self, transaction: object, command: DisablePluginInstallationCommand, *,
        session_token: bytes, csrf_token: bytes,
    ) -> None:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PluginActivationOwnerError("PLUGIN_DISABLE_UNAVAILABLE")
        try:
            actor = self._access.authorized_admin(
                transaction, session_token=session_token,
                csrf_token=csrf_token, now=now,
            )
        except Exception:
            raise PluginActivationOwnerError("PLUGIN_DISABLE_UNAVAILABLE") from None
        if type(actor) is not uuid.UUID or actor != command.actor_id:
            raise PluginActivationOwnerError("PLUGIN_DISABLE_AUTH_ACCESS_DENIED")

    def _require_license(self, trace_id: uuid.UUID) -> None:
        try:
            self._guard.require_valid(trace_id=trace_id)
        except RuntimeLicenseError:
            raise PluginActivationOwnerError(
                "PLUGIN_DISABLE_LICENSE_OPERATION_DENIED"
            ) from None
        except Exception:
            raise PluginActivationOwnerError("PLUGIN_DISABLE_UNAVAILABLE") from None

    @staticmethod
    def _map_owner_error(code: str) -> str:
        return {
            "PLUGIN_INSTALLATION_NOT_FOUND": "RESOURCE_NOT_FOUND",
            "PLUGIN_LOCK_VERSION_CONFLICT": "CONFLICT_VERSION",
            "PLUGIN_ACTIVATION_STATE_CONFLICT": "CONFLICT_STATE",
            "PLUGIN_CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
            "PLUGIN_DISABLE_AUTH_ACCESS_DENIED": "AUTH_ACCESS_DENIED",
            "PLUGIN_DISABLE_LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        }.get(code, "PLUGIN_DISABLE_UNAVAILABLE")

    @staticmethod
    def _validate(
        command: object, session_token: bytes, csrf_token: bytes,
    ) -> None:
        if (type(command) is not DisablePluginInstallationCommand
                or type(command.plugin_installation_id) is not uuid.UUID
                or command.plugin_installation_id.int == 0
                or type(command.actor_id) is not uuid.UUID or command.actor_id.int == 0
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 9_223_372_036_854_775_807
                or type(session_token) is not bytes or len(session_token) != 32
                or type(csrf_token) is not bytes or len(csrf_token) != 32):
            raise PluginInstallationDisableError("VALIDATION_FAILED")
