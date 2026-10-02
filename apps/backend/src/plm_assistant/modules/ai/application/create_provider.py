"""Internal AI-01 Provider registration; never activates or contacts a vendor."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderConfigurationError,
    ProviderKind,
)
from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataView
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class AIProviderCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateAIProvider:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    kind: ProviderKind
    display_name: str
    endpoint_policy_ref: str
    secret_ref: uuid.UUID
    data_region: str
    egress_class: str
    capabilities: frozenset[ProviderCapability]
    idempotency_key: str = field(repr=False)


class AIProviderCreateAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class AIProviderLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIProviderSecretProofPort(Protocol):
    def active_provider_key(self, transaction: object, *, secret_ref: uuid.UUID) -> bool: ...


class AIProviderCreateRepositoryPort(Protocol):
    def create(self, transaction: object, *, configuration: ProviderConfiguration,
               config_id: uuid.UUID, actor_id: uuid.UUID) -> None: ...

    def initial_config_id(self, transaction: object, *, provider_id: uuid.UUID) -> uuid.UUID | None: ...

    def initial_view(self, transaction: object, *, provider_id: uuid.UUID) -> AIProviderMetadataView | None: ...


class AIProviderReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AIProviderCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: AIProviderCreateAccessPort, license_guard: AIProviderLicensePort,
                 secret_proof: AIProviderSecretProofPort,
                 repository: AIProviderCreateRepositoryPort,
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

    def create(self, command: CreateAIProvider) -> uuid.UUID:
        result = self._create(command, include_view=False)
        if type(result) is not uuid.UUID:
            raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE")
        return result

    def create_view(self, command: CreateAIProvider) -> AIProviderMetadataView:
        """Return the immutable first response for HTTP creation and replay."""
        result = self._create(command, include_view=True)
        if type(result) is not AIProviderMetadataView:
            raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE")
        return result

    def _create(self, command: CreateAIProvider, *, include_view: bool) -> uuid.UUID | AIProviderMetadataView:
        if (type(command) is not CreateAIProvider
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise AIProviderCreateError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            provider_id = uuid.UUID(new_uuid7())
            config = ProviderConfiguration(
                provider_id=provider_id, config_version=1, kind=command.kind,
                display_name=command.display_name,
                endpoint_policy_ref=command.endpoint_policy_ref,
                secret_ref=command.secret_ref, data_region=command.data_region,
                egress_class=command.egress_class, capabilities=command.capabilities,
            )
            fingerprint = canonical_payload_fingerprint({
                "kind": config.kind.value, "display_name": config.display_name,
                "endpoint_policy_ref": config.endpoint_policy_ref,
                "secret_ref": str(config.secret_ref), "data_region": config.data_region,
                "egress_class": config.egress_class,
                "capabilities": sorted(item.value for item in config.capabilities),
            })
        except (IdempotencyError, ProviderConfigurationError):
            raise AIProviderCreateError("VALIDATION_FAILED") from None
        try:
            # Preserve the existing Auth-before-License ordering and recheck
            # the current session inside the eventual write transaction.
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_PROVIDER_CREATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != "V1_AI_PROVIDER_CREATE"
                            or replay.status_code != 201
                            or type(self._repo.initial_config_id(
                                tx, provider_id=replay.ref_id)) is not uuid.UUID):
                        raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE")
                    # A previous successful creation remains historically
                    # identifiable after its Secret is disabled; no use/activation.
                    if include_view:
                        view = self._repo.initial_view(tx, provider_id=replay.ref_id)
                        if type(view) is not AIProviderMetadataView:
                            raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE")
                        return view
                    return replay.ref_id
                if not self._secret.active_provider_key(tx, secret_ref=config.secret_ref):
                    raise AIProviderCreateError("AI_PROVIDER_SECRET_UNAVAILABLE")
                config_id = uuid.UUID(new_uuid7())
                self._repo.create(tx, configuration=config, config_id=config_id,
                                  actor_id=actor_id)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROVIDER_CREATE", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-01",
                    target_object_id=provider_id, target_version_id=config_id,
                    after_state="CONFIGURED",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROVIDER_CREATE", provider_id, 201,
                ))
                if include_view:
                    view = self._repo.initial_view(tx, provider_id=provider_id)
                    if type(view) is not AIProviderMetadataView:
                        raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE")
                tx.commit()
                return view if include_view else provider_id
        except AIProviderCreateError:
            raise
        except RuntimeLicenseError:
            raise AIProviderCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIProviderCreateError(exc.code) from None
        except Exception:
            raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE") from None

    def _require_admin(self, tx: object, command: CreateAIProvider) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIProviderCreateError("AI_PROVIDER_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise AIProviderCreateError("AUTH_ACCESS_DENIED")
        return actor_id
