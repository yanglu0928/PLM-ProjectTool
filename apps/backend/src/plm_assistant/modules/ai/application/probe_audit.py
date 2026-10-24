"""Safe SYSTEM audit for Provider Test terminal and retry transitions."""

from __future__ import annotations

import uuid
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim


class ProbeAuditError(RuntimeError):
    pass


class _Actor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class _Audit(Protocol):
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID: ...


class ProviderProbeAudit:
    def __init__(self, *, system_actor: _Actor, audit: _Audit) -> None:
        if system_actor is None or audit is None:
            raise ValueError("Provider probe audit dependencies required")
        self._actor, self._audit = system_actor, audit

    def capture(self) -> uuid.UUID:
        try:
            identity = self._actor.assert_current()
            if type(identity) is not uuid.UUID or not identity.int:
                raise ValueError("invalid SYSTEM actor")
            return identity
        except Exception:
            raise ProbeAuditError("PROBE_AUDIT_UNAVAILABLE") from None

    def append(self, transaction: object, *, claim: AIProviderTestClaim,
               actor_id: uuid.UUID, action: str, outcome: str,
               state: str, reason_code: str | None = None) -> None:
        if type(claim) is not AIProviderTestClaim:
            raise ProbeAuditError("PROBE_AUDIT_UNAVAILABLE")
        event_id = self._audit.append(transaction, AuditEventDraft(
            trace_id=claim.trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="SYSTEM",
            actor_id=actor_id, original_actor_id=claim.actor_id,
            actor_hint_digest=None, action=action, outcome=outcome,
            target_owner_module="ai", target_object_type="AI-01",
            target_object_id=claim.provider_id, target_version_id=claim.config_id,
            reason_code=reason_code, before_state="RUNNING", after_state=state,
        ))
        if type(event_id) is not uuid.UUID or not event_id.int:
            raise ProbeAuditError("PROBE_AUDIT_UNAVAILABLE")

    def assert_same(self, identity: uuid.UUID) -> None:
        if self.capture() != identity:
            raise ProbeAuditError("PROBE_AUDIT_UNAVAILABLE")
