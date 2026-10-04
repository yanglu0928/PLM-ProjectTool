"""Disposable PG18 Secret access audit and fail-closed resolver proof."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from plm_assistant.modules.ai.application.probe_policy import ProviderProbePlan
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightSnapshot
from plm_assistant.modules.ai.infrastructure.provider_probe_secret_audit import (
    ProviderProbeSecretAccessAudit, ProviderProbeSecretAuditError,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError, SecretConsumer, SecretEnvelope, SecretPurpose,
    SecretRef, SecretResolver, SecretState,
)
from plm_assistant.modules.platform.application.trace_context import trace_scope


parent = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p05-a01-job-read" / "verify.py"))
connect = parent["connect"]


class SystemActor:
    def __init__(self):
        self.id = uuid.uuid4()
        self.enabled = True

    def assert_current(self):
        if not self.enabled:
            raise RuntimeError("synthetic unavailable actor")
        return self.id


class Store:
    def __init__(self, envelope):
        self.envelope = envelope

    def load(self, _):
        return self.envelope


class Decryptor:
    def __init__(self):
        self.buffers = []

    def decrypt(self, _):
        value = bytearray(b"synthetic-key")
        self.buffers.append(value)
        return value


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit unavailable")


def after_success(*, runtime, name, actor, request, ref, guard, token,
                  result_id, policies, secret):
    del guard, token, result_id, policies
    claim = AIProviderTestClaim(
        ref.job_id, request.provider_id, request.config_id,
        request.config_version, request.secret_version_id, actor,
        request.trace_id, request.policy_sha256, 1, 1,
    )
    snapshot = ProviderTestPreflightSnapshot(
        claim, ProviderProbePlan(
            request.provider_id, request.config_version,
            "endpoint.synthetic.v1", "https://probe.example.test/v1/chat",
            "synthetic-chat", secret,
        ),
    )
    system = SystemActor()
    source = ProviderProbeSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()), system_actor=system,
    )
    secret_ref = SecretRef(secret)
    envelope = SecretEnvelope(
        secret_ref, SecretPurpose.AI_PROVIDER_KEY, SecretState.ACTIVE,
        SecretConsumer.AI_PROVIDER_ADAPTER, 1, b"synthetic-ciphertext",
        b"synthetic-metadata", "synthetic-only", request.secret_version_id,
    )
    decryptor = Decryptor()
    resolver = SecretResolver(Store(envelope), decryptor, source)
    try:
        source.record_access(secret_ref=secret_ref, consumer="AI_PROVIDER_ADAPTER",
                             outcome="GRANTED", trace_id=str(request.trace_id))
    except ProviderProbeSecretAuditError:
        pass
    else:
        raise AssertionError("unbound Secret audit unexpectedly granted")
    with source.bind(snapshot), trace_scope(str(request.trace_id)):
        with resolver.use(secret_ref, SecretConsumer.AI_PROVIDER_ADAPTER,
                          expected_version_id=request.secret_version_id) as value:
            assert bytes(value) == b"synthetic-key"
        assert not any(decryptor.buffers[-1])
    with connect(name) as db:
        rows = db.execute(
            "SELECT actor_type,actor_id,original_actor_id,trace_id,action,outcome,"
            "target_object_id,target_version_id FROM plm.aud_events "
            "WHERE action='AI_PROVIDER_SECRET_ACCESS' AND target_object_id=%s",
            (secret,),
        ).fetchall()
        assert rows == [("SYSTEM", system.id, actor, request.trace_id,
                         "AI_PROVIDER_SECRET_ACCESS", "SUCCESS", secret,
                         request.secret_version_id)]
    broken = ProviderProbeSecretAccessAudit(
        unit_of_work=runtime.unit_of_work, audit=FailedAudit(), system_actor=system,
    )
    blocked_decryptor = Decryptor()
    blocked = SecretResolver(Store(envelope), blocked_decryptor, broken)
    with broken.bind(snapshot), trace_scope(str(request.trace_id)):
        try:
            with blocked.use(secret_ref, SecretConsumer.AI_PROVIDER_ADAPTER,
                             expected_version_id=request.secret_version_id):
                raise AssertionError("audit failure leaked Secret")
        except SecretAccessError:
            pass
        else:
            raise AssertionError("audit failure unexpectedly granted Secret")
    assert blocked_decryptor.buffers and not any(blocked_decryptor.buffers[-1])
    with connect(name) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_SECRET_ACCESS' "
            "AND target_object_id=%s", (secret,),
        ).fetchone()[0] == 1
    print("PASS: PG18 bound SYSTEM/original user Secret audit, zeroized denied access and no extra event")


if __name__ == "__main__":
    parent["main"](after_success=after_success)
