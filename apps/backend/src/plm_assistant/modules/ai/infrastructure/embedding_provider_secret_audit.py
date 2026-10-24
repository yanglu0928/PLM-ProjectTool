"""Scope-aware Secret access audit for one authorized Embedding send."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    provider_route_fingerprint,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.secret_access import SecretRef


class AIEmbeddingSecretAuditError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Embedding Secret audit unavailable")


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


@dataclass(frozen=True, slots=True)
class _BoundIdentity:
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    requested_by: uuid.UUID
    job_id: uuid.UUID
    embedding_build_id: uuid.UUID
    embedding_build_batch_id: uuid.UUID
    secret_ref: uuid.UUID
    secret_version_id: uuid.UUID


class AIEmbeddingProviderSecretAccessAudit:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 audit: AuditService, system_actor: _SystemActor) -> None:
        if any(value is None for value in (unit_of_work, audit, system_actor)):
            raise ValueError("AI Embedding Secret audit dependencies required")
        self._uow = unit_of_work
        self._audit = audit
        self._actor = system_actor
        self._bound: ContextVar[_BoundIdentity | None] = ContextVar(
            "ai_embedding_provider_secret_audit_scope", default=None,
        )

    @contextmanager
    def bind(self, envelope: AIEmbeddingEnvelope,
             send: AuthorizedAIEmbeddingSend) -> Iterator[None]:
        try:
            if (self._bound.get() is not None
                    or type(envelope) is not AIEmbeddingEnvelope
                    or type(send) is not AuthorizedAIEmbeddingSend):
                raise AIEmbeddingSecretAuditError()
            envelope.__post_init__()
            send.__post_init__()
            route, proof = send.route, send.proof
            if (proof.embedding_build_id != envelope.embedding_build_id
                    or proof.embedding_build_batch_id
                    != envelope.embedding_build_batch_id
                    or not hmac.compare_digest(
                        proof.payload_fingerprint,
                        envelope.payload_fingerprint)
                    or proof.payload_bytes != envelope.payload_bytes
                    or proof.input_tokens != envelope.input_tokens
                    or not hmac.compare_digest(
                        proof.route_fingerprint,
                        provider_route_fingerprint(route))):
                raise AIEmbeddingSecretAuditError()
            identity = _BoundIdentity(
                proof.trace_id, proof.scope, proof.project_id, proof.actor_id,
                proof.job_id, proof.embedding_build_id,
                proof.embedding_build_batch_id, route.secret_ref,
                route.secret_version_id,
            )
        except Exception:
            raise AIEmbeddingSecretAuditError() from None
        token = self._bound.set(identity)
        try:
            yield
        finally:
            self._bound.reset(token)

    def record_access(self, *, secret_ref: SecretRef, consumer: str,
                      outcome: str, trace_id: str) -> None:
        identity = self._bound.get()
        try:
            if (type(identity) is not _BoundIdentity
                    or type(secret_ref) is not SecretRef
                    or secret_ref.secret_id != identity.secret_ref
                    or consumer != "AI_PROVIDER_ADAPTER"
                    or outcome not in ("GRANTED", "DENIED")
                    or type(trace_id) is not str
                    or trace_id != str(identity.trace_id)):
                raise AIEmbeddingSecretAuditError()
            system_id = self._actor.assert_current()
            if type(system_id) is not uuid.UUID or not system_id.int:
                raise AIEmbeddingSecretAuditError()
            event_scope = "PROJECT" if identity.scope == "PROJECT" else "DEPLOYMENT"
            target_project_id = (
                identity.project_id if event_scope == "PROJECT" else None
            )
            with self._uow() as transaction:
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=identity.trace_id,
                    event_scope=event_scope,
                    target_project_id=target_project_id,
                    actor_type="SYSTEM", actor_id=system_id,
                    original_actor_id=identity.requested_by,
                    actor_hint_digest=None,
                    action="AI_PROVIDER_SECRET_ACCESS",
                    outcome="SUCCESS" if outcome == "GRANTED" else "DENIED",
                    target_owner_module="platform",
                    target_object_type="PLT-02",
                    target_object_id=identity.secret_ref,
                    target_version_id=identity.secret_version_id,
                    after_state="RAG_EMBEDDING_SEND",
                ))
                if type(event_id) is not uuid.UUID or not event_id.int:
                    raise AIEmbeddingSecretAuditError()
                if self._actor.assert_current() != system_id:
                    raise AIEmbeddingSecretAuditError()
                transaction.commit()
        except Exception:
            raise AIEmbeddingSecretAuditError() from None
