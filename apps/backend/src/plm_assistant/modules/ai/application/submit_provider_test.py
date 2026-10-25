"""Authorized, atomic Provider Test request; no probe execution or egress."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.probe_policy import (
    EndpointProbeRegistry, ProbePolicyError, probe_policy_sha256,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderConfiguration
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import (
    AIProviderTestEnqueueError, AIProviderTestJobQueue, AIProviderTestJobRef,
    AIProviderTestJobRequest,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class AIProviderTestSubmitError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SubmitAIProviderTest:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    provider_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CurrentProviderTestSource:
    config_id: uuid.UUID
    lock_version: int
    state: str
    configuration: ProviderConfiguration


class _Access(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class _License(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class _Source(Protocol):
    def lock_current(self, transaction: object, *, provider_id: uuid.UUID) -> CurrentProviderTestSource | None: ...


class _Secret(Protocol):
    def active_provider_key_version(self, transaction: object, *, secret_ref: uuid.UUID) -> uuid.UUID | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AIProviderTestSubmitService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: _License, source: _Source, secret_proof: _Secret,
                 probe_registry: EndpointProbeRegistry, queue: AIProviderTestJobQueue,
                 receipts: _Receipts, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard, source,
                                           secret_proof, probe_registry, queue, receipts, audit)):
            raise ValueError("Provider Test submit dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._source, self._secret, self._registry = source, secret_proof, probe_registry
        self._queue, self._receipts, self._audit = queue, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(self, command: SubmitAIProviderTest) -> AIProviderTestJobRef:
        if (type(command) is not SubmitAIProviderTest
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or not command.trace_id.int
                or type(command.provider_id) is not uuid.UUID or not command.provider_id.int
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775807):
            raise AIProviderTestSubmitError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "provider_id": str(command.provider_id),
                "expected_lock_version": command.expected_lock_version,
                "operation": "V1_AI_PROVIDER_TEST",
            })
        except IdempotencyError:
            raise AIProviderTestSubmitError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_PROVIDER_TEST", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != "V1_AI_PROVIDER_TEST" or replay.status_code != 202:
                        raise AIProviderTestSubmitError("AI_PROVIDER_UNAVAILABLE")
                    original = self._queue.find_by_job(
                        tx, job_id=replay.ref_id, provider_id=command.provider_id, actor_id=actor_id,
                    )
                    if original is None:
                        raise AIProviderTestSubmitError("AI_PROVIDER_UNAVAILABLE")
                    return original
                current = self._source.lock_current(tx, provider_id=command.provider_id)
                if current is None:
                    raise AIProviderTestSubmitError("AI_PROVIDER_NOT_FOUND")
                if current.lock_version != command.expected_lock_version:
                    raise AIProviderTestSubmitError("CONFLICT_VERSION")
                if current.state not in {"CONFIGURED", "SUSPENDED", "ACTIVE"}:
                    raise AIProviderTestSubmitError("AI_PROVIDER_STATE_CONFLICT")
                try:
                    plan = self._registry.plan(current.configuration)
                except ProbePolicyError:
                    raise AIProviderTestSubmitError("AI_PROVIDER_POLICY_UNAVAILABLE") from None
                secret_version = self._secret.active_provider_key_version(
                    tx, secret_ref=plan.secret_ref,
                )
                if type(secret_version) is not uuid.UUID or not secret_version.int:
                    raise AIProviderTestSubmitError("AI_PROVIDER_SECRET_UNAVAILABLE")
                policy_sha = probe_policy_sha256(current.configuration, plan)
                request = AIProviderTestJobRequest(
                    submission_id=uuid.UUID(new_uuid7()), provider_id=command.provider_id,
                    config_id=current.config_id, config_version=current.configuration.config_version,
                    secret_version_id=secret_version, actor_id=actor_id,
                    trace_id=command.trace_id, policy_sha256=policy_sha,
                )
                job = self._queue.enqueue(tx, request=request)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROVIDER_TEST_REQUESTED", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-01",
                    target_object_id=command.provider_id, target_version_id=current.config_id,
                    after_state="TEST_QUEUED",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROVIDER_TEST", job.job_id, 202,
                ))
                tx.commit()
                return job
        except AIProviderTestSubmitError:
            raise
        except RuntimeLicenseError:
            raise AIProviderTestSubmitError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIProviderTestSubmitError(exc.code) from None
        except AIProviderTestEnqueueError:
            raise AIProviderTestSubmitError("AI_PROVIDER_UNAVAILABLE") from None
        except Exception:
            raise AIProviderTestSubmitError("AI_PROVIDER_UNAVAILABLE") from None

    def _require_admin(self, tx: object, command: SubmitAIProviderTest) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIProviderTestSubmitError("AI_PROVIDER_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or not actor_id.int:
            raise AIProviderTestSubmitError("AUTH_ACCESS_DENIED")
        return actor_id
