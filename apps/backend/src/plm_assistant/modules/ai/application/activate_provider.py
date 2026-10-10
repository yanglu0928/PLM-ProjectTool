"""Authorized Provider activation; no vendor call or public HTTP exposure."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.provider_activation_proof import (
    ProviderActivationProof, ProviderActivationProofError, ProviderActivationProofService,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class AIProviderActivationError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ActivateAIProvider:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    provider_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ActivatedAIProvider:
    activation_result_id: uuid.UUID
    provider_id: uuid.UUID
    config_id: uuid.UUID
    proof_result_id: uuid.UUID
    actor_id: uuid.UUID
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    before_state: str
    expected_lock_version: int
    lock_version: int
    state: str = "ACTIVE"

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.activation_result_id, self.provider_id, self.config_id,
                self.proof_result_id, self.actor_id, self.audit_event_id, self.trace_id))
                or self.before_state not in ("CONFIGURED", "SUSPENDED")
                or self.state != "ACTIVE"
                or type(self.expected_lock_version) is not int
                or not 0 <= self.expected_lock_version <= 9223372036854775806
                or type(self.lock_version) is not int
                or self.lock_version != self.expected_lock_version + 1):
            raise AIProviderActivationError()

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


class _Access(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class _Repository(Protocol):
    def activate(self, transaction: object, *, proof: ProviderActivationProof,
                 expected_lock_version: int) -> int: ...
    def save(self, transaction: object, *, result: ActivatedAIProvider) -> None: ...
    def get(self, transaction: object, *, result_id: uuid.UUID, provider_id: uuid.UUID,
            actor_id: uuid.UUID, expected_lock_version: int) -> ActivatedAIProvider | None: ...


class AIProviderActivationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: object, proof: ProviderActivationProofService,
                 repository: _Repository, receipts: _Receipts, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard, proof,
                                           repository, receipts, audit)):
            raise ValueError("AI Provider activation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._proof, self._repo, self._receipts, self._audit = proof, repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def activate(self, command: ActivateAIProvider) -> ActivatedAIProvider:
        if (type(command) is not ActivateAIProvider
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or not command.trace_id.int
                or type(command.provider_id) is not uuid.UUID or not command.provider_id.int
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806):
            raise AIProviderActivationError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "provider_id": str(command.provider_id),
                "expected_lock_version": command.expected_lock_version,
                "operation": "V1_AI_PROVIDER_ACTIVATE",
            })
        except IdempotencyError:
            raise AIProviderActivationError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_PROVIDER_ACTIVATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != "V1_AI_PROVIDER_ACTIVATE"
                            or replay.status_code != 200):
                        raise AIProviderActivationError()
                    original = self._repo.get(
                        tx, result_id=replay.ref_id, provider_id=command.provider_id,
                        actor_id=actor_id,
                        expected_lock_version=command.expected_lock_version,
                    )
                    if type(original) is not ActivatedAIProvider:
                        raise AIProviderActivationError()
                    original.__post_init__()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return original
                proof = self._proof.require_locked(
                    tx, provider_id=command.provider_id, trace_id=command.trace_id,
                )
                if type(proof) is not ProviderActivationProof:
                    raise AIProviderActivationError()
                if proof.lock_version != command.expected_lock_version:
                    raise AIProviderActivationError("CONFLICT_VERSION")
                if proof.state not in ("CONFIGURED", "SUSPENDED"):
                    raise AIProviderActivationError("AI_PROVIDER_STATE_CONFLICT")
                lock_version = self._repo.activate(
                    tx, proof=proof, expected_lock_version=command.expected_lock_version,
                )
                if lock_version != command.expected_lock_version + 1:
                    raise AIProviderActivationError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROVIDER_ACTIVATED", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-01",
                    target_object_id=command.provider_id, target_version_id=proof.config_id,
                    before_state=proof.state, after_state="ACTIVE",
                ))
                result = ActivatedAIProvider(
                    uuid.UUID(new_uuid7()), command.provider_id, proof.config_id,
                    proof.result_id, actor_id, audit_id, command.trace_id,
                    proof.state, command.expected_lock_version, lock_version,
                )
                result.__post_init__()
                self._repo.save(tx, result=result)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROVIDER_ACTIVATE", result.activation_result_id, 200,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except AIProviderActivationError:
            raise
        except ProviderActivationProofError as exc:
            raise AIProviderActivationError(exc.code) from None
        except RuntimeLicenseError:
            raise AIProviderActivationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIProviderActivationError(exc.code) from None
        except Exception:
            raise AIProviderActivationError() from None

    def _require_admin(self, tx: object, command: ActivateAIProvider) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIProviderActivationError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise AIProviderActivationError("AUTH_ACCESS_DENIED")
        return actor
