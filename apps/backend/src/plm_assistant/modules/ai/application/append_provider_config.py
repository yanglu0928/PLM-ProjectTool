"""Append an immutable Provider configuration without switching an ACTIVE provider."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.create_provider import (
    AIProviderCreateAccessPort, AIProviderLicensePort, AIProviderReceiptPort,
    AIProviderSecretProofPort,
)
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderConfigurationError, ProviderKind,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class AIProviderAppendError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AppendAIProviderConfig:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    provider_id: uuid.UUID
    expected_lock_version: int
    kind: ProviderKind
    display_name: str
    endpoint_policy_ref: str
    secret_ref: uuid.UUID
    data_region: str
    egress_class: str
    capabilities: frozenset[ProviderCapability]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PatchAIProviderConfig:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    provider_id: uuid.UUID
    expected_lock_version: int
    changes: dict[str, object] = field(repr=False)
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CurrentAIProvider:
    state: str
    lock_version: int
    config_version: int
    kind: ProviderKind


@dataclass(frozen=True, slots=True)
class AppendedAIProviderConfigResult:
    provider_id: uuid.UUID
    config_id: uuid.UUID
    config_version: int
    lock_version: int

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


class AIProviderAppendRepositoryPort(Protocol):
    def lock_current(self, transaction: object, *, provider_id: uuid.UUID) -> CurrentAIProvider | None: ...

    def version_belongs(self, transaction: object, *, provider_id: uuid.UUID,
                        config_id: uuid.UUID) -> bool: ...

    def version_number(self, transaction: object, *, provider_id: uuid.UUID,
                       config_id: uuid.UUID) -> int | None: ...

    def current_configuration(self, transaction: object, *, provider_id: uuid.UUID) -> ProviderConfiguration | None: ...

    def append(self, transaction: object, *, configuration: ProviderConfiguration,
               config_id: uuid.UUID, actor_id: uuid.UUID, expected_lock_version: int) -> None: ...


class AIProviderAppendService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: AIProviderCreateAccessPort, license_guard: AIProviderLicensePort,
                 secret_proof: AIProviderSecretProofPort,
                 repository: AIProviderAppendRepositoryPort,
                 receipts: AIProviderReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard,
                                         secret_proof, repository, receipts, audit)):
            raise ValueError("AI Provider dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._secret, self._repo, self._receipts, self._audit = (
            secret_proof, repository, receipts, audit,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def append(self, command: AppendAIProviderConfig) -> uuid.UUID:
        result = self._append(command, include_result=False)
        if type(result) is not uuid.UUID:
            raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
        return result

    def append_result(self, command: AppendAIProviderConfig) -> AppendedAIProviderConfigResult:
        """Return the original version/ETag for the frozen PATCH boundary."""
        result = self._append(command, include_result=True)
        if type(result) is not AppendedAIProviderConfigResult:
            raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
        return result

    def patch_result(self, command: PatchAIProviderConfig) -> AppendedAIProviderConfigResult:
        """Apply a controlled partial configuration in the locked transaction."""
        if (type(command) is not PatchAIProviderConfig
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.provider_id) is not uuid.UUID or command.provider_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 9223372036854775807
                or type(command.changes) is not dict or not command.changes):
            raise AIProviderAppendError("VALIDATION_FAILED")
        changes = dict(command.changes)
        allowed = frozenset({
            "display_name", "endpoint_policy_ref", "secret_ref", "data_region",
            "egress_class", "capabilities",
        })
        if set(changes) - allowed:
            raise AIProviderAppendError("VALIDATION_FAILED")
        if any(type(value) is not str for key, value in changes.items()
               if key in allowed - {"secret_ref", "capabilities"}):
            raise AIProviderAppendError("VALIDATION_FAILED")
        if ("secret_ref" in changes and (
                type(changes["secret_ref"]) is not uuid.UUID
                or changes["secret_ref"].int == 0)):
            raise AIProviderAppendError("VALIDATION_FAILED")
        if ("capabilities" in changes and (
                type(changes["capabilities"]) is not frozenset
                or not changes["capabilities"]
                or any(type(item) is not ProviderCapability for item in changes["capabilities"]))):
            raise AIProviderAppendError("VALIDATION_FAILED")
        fingerprint_changes = {
            key: (str(value) if key == "secret_ref" else
                  sorted(item.value for item in value) if key == "capabilities" else value)
            for key, value in changes.items()
        }
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "provider_id": str(command.provider_id),
                "expected_lock_version": command.expected_lock_version,
                "changes": fingerprint_changes,
            })
        except IdempotencyError as exc:
            raise AIProviderAppendError(exc.code) from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_PROVIDER_CONFIG_PATCH", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != "V1_AI_PROVIDER_CONFIG_PATCH"
                            or replay.status_code != 200
                            or not self._repo.version_belongs(
                                tx, provider_id=command.provider_id, config_id=replay.ref_id)):
                        raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                    number = self._repo.version_number(
                        tx, provider_id=command.provider_id, config_id=replay.ref_id,
                    )
                    if type(number) is not int or number < 2:
                        raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                    return AppendedAIProviderConfigResult(
                        command.provider_id, replay.ref_id, number,
                        command.expected_lock_version + 1,
                    )
                current = self._repo.lock_current(tx, provider_id=command.provider_id)
                if current is None:
                    raise AIProviderAppendError("RESOURCE_NOT_FOUND")
                if current.state not in ("CONFIGURED", "SUSPENDED"):
                    raise AIProviderAppendError("AI_PROVIDER_STATE_CONFLICT")
                if current.lock_version != command.expected_lock_version:
                    raise AIProviderAppendError("CONFLICT_VERSION")
                if current.config_version >= 2147483647:
                    raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                base = self._repo.current_configuration(tx, provider_id=command.provider_id)
                if (type(base) is not ProviderConfiguration
                        or base.config_version != current.config_version
                        or base.kind is not current.kind):
                    raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                try:
                    configuration = ProviderConfiguration(
                        provider_id=command.provider_id,
                        config_version=current.config_version + 1,
                        kind=base.kind,
                        display_name=changes.get("display_name", base.display_name),
                        endpoint_policy_ref=changes.get("endpoint_policy_ref", base.endpoint_policy_ref),
                        secret_ref=changes.get("secret_ref", base.secret_ref),
                        data_region=changes.get("data_region", base.data_region),
                        egress_class=changes.get("egress_class", base.egress_class),
                        capabilities=changes.get("capabilities", base.capabilities),
                    )
                except ProviderConfigurationError:
                    raise AIProviderAppendError("VALIDATION_FAILED") from None
                if not self._secret.active_provider_key(tx, secret_ref=configuration.secret_ref):
                    raise AIProviderAppendError("AI_PROVIDER_SECRET_UNAVAILABLE")
                config_id = uuid.UUID(new_uuid7())
                self._repo.append(tx, configuration=configuration, config_id=config_id,
                                  actor_id=actor_id,
                                  expected_lock_version=command.expected_lock_version)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROVIDER_CONFIG_APPEND", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-01",
                    target_object_id=command.provider_id, target_version_id=config_id,
                    before_state=current.state, after_state=current.state,
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROVIDER_CONFIG_PATCH", config_id, 200,
                ))
                result = AppendedAIProviderConfigResult(
                    command.provider_id, config_id, configuration.config_version,
                    command.expected_lock_version + 1,
                )
                tx.commit()
                return result
        except AIProviderAppendError:
            raise
        except RuntimeLicenseError:
            raise AIProviderAppendError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIProviderAppendError(exc.code) from None
        except Exception:
            raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE") from None

    def _append(self, command: AppendAIProviderConfig, *, include_result: bool) -> uuid.UUID | AppendedAIProviderConfigResult:
        if (type(command) is not AppendAIProviderConfig
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.provider_id) is not uuid.UUID or command.provider_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 9223372036854775807):
            raise AIProviderAppendError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            candidate = self._configuration(command, version=1)
            fingerprint = canonical_payload_fingerprint({
                "provider_id": str(command.provider_id),
                "expected_lock_version": command.expected_lock_version,
                "kind": candidate.kind.value, "display_name": candidate.display_name,
                "endpoint_policy_ref": candidate.endpoint_policy_ref,
                "secret_ref": str(candidate.secret_ref), "data_region": candidate.data_region,
                "egress_class": candidate.egress_class,
                "capabilities": sorted(item.value for item in candidate.capabilities),
            })
        except (IdempotencyError, ProviderConfigurationError):
            raise AIProviderAppendError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_PROVIDER_CONFIG_APPEND", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != "V1_AI_PROVIDER_CONFIG_APPEND"
                            or replay.status_code != 201
                            or not self._repo.version_belongs(
                                tx, provider_id=command.provider_id, config_id=replay.ref_id)):
                        raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                    if include_result:
                        number = self._repo.version_number(
                            tx, provider_id=command.provider_id, config_id=replay.ref_id,
                        )
                        if type(number) is not int or number < 2:
                            raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                        return AppendedAIProviderConfigResult(
                            command.provider_id, replay.ref_id, number,
                            command.expected_lock_version + 1,
                        )
                    return replay.ref_id
                current = self._repo.lock_current(tx, provider_id=command.provider_id)
                if current is None:
                    raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                if current.state not in ("CONFIGURED", "SUSPENDED"):
                    raise AIProviderAppendError("AI_PROVIDER_STATE_CONFLICT")
                if current.lock_version != command.expected_lock_version:
                    raise AIProviderAppendError("CONFLICT_VERSION")
                if current.kind is not command.kind:
                    raise AIProviderAppendError("AI_PROVIDER_KIND_CONFLICT")
                if current.config_version >= 2147483647:
                    raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
                if not self._secret.active_provider_key(tx, secret_ref=candidate.secret_ref):
                    raise AIProviderAppendError("AI_PROVIDER_SECRET_UNAVAILABLE")
                configuration = self._configuration(command, version=current.config_version + 1)
                config_id = uuid.UUID(new_uuid7())
                self._repo.append(tx, configuration=configuration, config_id=config_id,
                                  actor_id=actor_id,
                                  expected_lock_version=command.expected_lock_version)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROVIDER_CONFIG_APPEND", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-01",
                    target_object_id=command.provider_id, target_version_id=config_id,
                    before_state=current.state, after_state=current.state,
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROVIDER_CONFIG_APPEND", config_id, 201,
                ))
                result = AppendedAIProviderConfigResult(
                    command.provider_id, config_id, configuration.config_version,
                    command.expected_lock_version + 1,
                ) if include_result else config_id
                tx.commit()
                return result
        except AIProviderAppendError:
            raise
        except RuntimeLicenseError:
            raise AIProviderAppendError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIProviderAppendError(exc.code) from None
        except Exception:
            raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE") from None

    @staticmethod
    def _configuration(command: AppendAIProviderConfig, *, version: int) -> ProviderConfiguration:
        return ProviderConfiguration(
            provider_id=command.provider_id, config_version=version, kind=command.kind,
            display_name=command.display_name,
            endpoint_policy_ref=command.endpoint_policy_ref, secret_ref=command.secret_ref,
            data_region=command.data_region, egress_class=command.egress_class,
            capabilities=command.capabilities,
        )

    def _require_admin(self, tx: object, command: AppendAIProviderConfig | PatchAIProviderConfig) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIProviderAppendError("AI_PROVIDER_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise AIProviderAppendError("AUTH_ACCESS_DENIED")
        return actor_id
