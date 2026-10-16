"""Project-scoped Secret access audit for one authorized AI Task send."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.application.provider_execution_contract import (
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AuthorizedAIProviderSend,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    execution_grant_fingerprint,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    PreparedAITaskInvocation,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.secret_access import SecretRef


class AITaskSecretAuditError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Task Secret audit unavailable")


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


@dataclass(frozen=True, slots=True)
class _BoundIdentity:
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    ai_task_id: uuid.UUID
    ai_invocation_id: uuid.UUID
    job_id: uuid.UUID
    attempt_no: int
    fencing_token: int
    secret_ref: uuid.UUID
    secret_version_id: uuid.UUID


class AITaskProviderSecretAccessAudit:
    """Bind exact no-content send facts before SecretResolver may audit access."""

    def __init__(
        self, *, unit_of_work: Callable[[], object], audit: AuditService,
        system_actor: _SystemActor,
    ) -> None:
        if any(value is None for value in (unit_of_work, audit, system_actor)):
            raise ValueError("AI Task Secret audit dependencies required")
        self._uow = unit_of_work
        self._audit = audit
        self._actor = system_actor
        self._bound: ContextVar[_BoundIdentity | None] = ContextVar(
            "ai_task_provider_secret_audit_scope", default=None,
        )

    @contextmanager
    def bind(
        self, prepared: PreparedAITaskInvocation,
        send: AuthorizedAIProviderSend,
    ) -> Iterator[None]:
        try:
            if (self._bound.get() is not None
                    or type(prepared) is not PreparedAITaskInvocation
                    or type(send) is not AuthorizedAIProviderSend):
                raise AITaskSecretAuditError()
            prepared.__post_init__()
            send.__post_init__()
            grant, route, proof = prepared.grant, send.route, send.proof
            if (proof.ai_task_id != grant.ai_task_id
                    or proof.job_id != grant.job_id
                    or proof.attempt_no != grant.attempt_no
                    or proof.fencing_token != grant.fencing_token
                    or proof.content_plan_id != grant.content_plan_id
                    or proof.authorization_ref != grant.authorization_ref
                    or not hmac.compare_digest(
                        proof.payload_fingerprint,
                        prepared.envelope.payload_fingerprint,
                    )
                    or proof.payload_bytes != prepared.envelope.payload_bytes
                    or proof.input_tokens != prepared.envelope.input_tokens
                    or not hmac.compare_digest(
                        proof.grant_fingerprint,
                        execution_grant_fingerprint(grant),
                    )
                    or not hmac.compare_digest(
                        proof.route_fingerprint,
                        provider_route_fingerprint(route),
                    )
                    or route.ai_provider_id != grant.ai_provider_id
                    or route.provider_config_version_id
                    != grant.provider_config_version_id
                    or route.ai_model_id != grant.ai_model_id):
                raise AITaskSecretAuditError()
            identity = _BoundIdentity(
                grant.trace_id, grant.project_id, grant.requested_by,
                grant.ai_task_id, proof.ai_invocation_id, grant.job_id,
                grant.attempt_no, grant.fencing_token, route.secret_ref,
                route.secret_version_id,
            )
        except Exception:
            raise AITaskSecretAuditError() from None
        token = self._bound.set(identity)
        try:
            yield
        finally:
            self._bound.reset(token)

    def record_access(
        self, *, secret_ref: SecretRef, consumer: str,
        outcome: str, trace_id: str,
    ) -> None:
        identity = self._bound.get()
        try:
            if (type(identity) is not _BoundIdentity
                    or type(secret_ref) is not SecretRef
                    or secret_ref.secret_id != identity.secret_ref
                    or consumer != "AI_PROVIDER_ADAPTER"
                    or outcome not in ("GRANTED", "DENIED")
                    or type(trace_id) is not str
                    or trace_id != str(identity.trace_id)):
                raise AITaskSecretAuditError()
            system_id = self._actor.assert_current()
            if type(system_id) is not uuid.UUID or not system_id.int:
                raise AITaskSecretAuditError()
            with self._uow() as transaction:
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=identity.trace_id,
                    event_scope="PROJECT",
                    target_project_id=identity.project_id,
                    actor_type="SYSTEM",
                    actor_id=system_id,
                    original_actor_id=identity.requested_by,
                    actor_hint_digest=None,
                    action="AI_PROVIDER_SECRET_ACCESS",
                    outcome="SUCCESS" if outcome == "GRANTED" else "DENIED",
                    target_owner_module="platform",
                    target_object_type="PLT-02",
                    target_object_id=identity.secret_ref,
                    target_version_id=identity.secret_version_id,
                    after_state="AI_TASK_SEND",
                ))
                if type(event_id) is not uuid.UUID or not event_id.int:
                    raise AITaskSecretAuditError()
                if self._actor.assert_current() != system_id:
                    raise AITaskSecretAuditError()
                transaction.commit()
        except Exception:
            raise AITaskSecretAuditError() from None
