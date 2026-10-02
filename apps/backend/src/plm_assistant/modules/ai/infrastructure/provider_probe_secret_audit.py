"""Scoped, persistent Secret access audit for an authorized Provider probe."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightSnapshot
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.secret_access import SecretRef


class ProviderProbeSecretAuditError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Provider probe Secret audit unavailable")


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class ProviderProbeSecretAccessAudit:
    """No ambient identity: caller binds a freshly checked Job snapshot."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 audit: AuditService, system_actor: _SystemActor) -> None:
        if any(item is None for item in (unit_of_work, audit, system_actor)):
            raise ValueError("Provider probe Secret audit dependencies required")
        self._uow, self._audit, self._actor = unit_of_work, audit, system_actor
        self._bound: ContextVar[ProviderTestPreflightSnapshot | None] = ContextVar(
            "provider_probe_secret_audit_scope", default=None,
        )

    @contextmanager
    def bind(self, snapshot: ProviderTestPreflightSnapshot) -> Iterator[None]:
        try:
            if (self._bound.get() is not None
                    or type(snapshot) is not ProviderTestPreflightSnapshot):
                raise ProviderProbeSecretAuditError()
            snapshot.claim.__post_init__()
            snapshot.plan.__post_init__()
            if (snapshot.plan.provider_id != snapshot.claim.provider_id
                    or snapshot.plan.config_version != snapshot.claim.config_version
                    or snapshot.plan.probe_id != snapshot.claim.probe_id):
                raise ProviderProbeSecretAuditError()
        except Exception:
            raise ProviderProbeSecretAuditError() from None
        token = self._bound.set(snapshot)
        try:
            yield
        finally:
            self._bound.reset(token)

    def record_access(self, *, secret_ref: SecretRef, consumer: str,
                      outcome: str, trace_id: str) -> None:
        snapshot = self._bound.get()
        try:
            if (type(snapshot) is not ProviderTestPreflightSnapshot
                    or type(secret_ref) is not SecretRef
                    or secret_ref.secret_id != snapshot.plan.secret_ref
                    or consumer != "AI_PROVIDER_ADAPTER"
                    or outcome not in ("GRANTED", "DENIED")
                    or type(trace_id) is not str
                    or trace_id != str(snapshot.claim.trace_id)):
                raise ProviderProbeSecretAuditError()
            system_id = self._actor.assert_current()
            if type(system_id) is not uuid.UUID or not system_id.int:
                raise ProviderProbeSecretAuditError()
            with self._uow() as tx:
                event_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=snapshot.claim.trace_id,
                    event_scope="DEPLOYMENT", target_project_id=None,
                    actor_type="SYSTEM", actor_id=system_id,
                    original_actor_id=snapshot.claim.actor_id,
                    actor_hint_digest=None, action="AI_PROVIDER_SECRET_ACCESS",
                    outcome="SUCCESS" if outcome == "GRANTED" else "DENIED",
                    target_owner_module="platform", target_object_type="PLT-02",
                    target_object_id=secret_ref.secret_id,
                    target_version_id=snapshot.claim.secret_version_id,
                ))
                if type(event_id) is not uuid.UUID or not event_id.int:
                    raise ProviderProbeSecretAuditError()
                if self._actor.assert_current() != system_id:
                    raise ProviderProbeSecretAuditError()
                tx.commit()
        except Exception:
            raise ProviderProbeSecretAuditError() from None
