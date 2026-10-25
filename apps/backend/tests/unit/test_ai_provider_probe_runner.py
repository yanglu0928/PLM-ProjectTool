from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace

from plm_assistant.modules.ai.application.probe_policy import ProviderProbePlan
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightSnapshot
from plm_assistant.modules.ai.application.run_provider_probe import (
    ProviderProbeExecutionError, ProviderProbeRunner,
)
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef, SecretResolver, SecretState,
)
from plm_assistant.modules.platform.application.trace_context import current_trace_id


class FakePreflight:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0
        self.next_result = None

    def preflight(self, **_):
        self.calls += 1
        return self.next_result if self.next_result is not None and self.calls == 2 else self.snapshot


class FakeConnection:
    def __init__(self):
        self.calls = 0
        self.key = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def send_fixed_probe(self, key):
        self.calls += 1
        self.key = key.tobytes()
        self.trace = current_trace_id()


class FakeTransport:
    def __init__(self):
        self.connection = FakeConnection()
        self.opened = 0

    def open(self, _):
        self.opened += 1
        return self.connection


class FakeStore:
    def __init__(self, envelope):
        self.envelope = envelope

    def load(self, _):
        return self.envelope


class FakeDecryptor:
    def __init__(self):
        self.value = bytearray(b"synthetic-key")
        self.calls = 0

    def decrypt(self, _):
        self.calls += 1
        return self.value


class FakeAudit:
    def record_access(self, **_):
        pass


class FakeAuditScope:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.bound = None
        self.trace = None

    @contextmanager
    def bind(self, snapshot):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.bound = snapshot
        self.trace = current_trace_id()
        try:
            yield
        finally:
            self.bound = None


class ProbeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.trace = uuid.uuid4()
        self.plan = ProviderProbePlan(
            uuid.uuid4(), 1, "trusted.synthetic", "https://probe.example.test/v1/chat",
            "synthetic-chat", uuid.uuid4(),
        )
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), self.plan.provider_id, uuid.uuid4(), 1,
            uuid.uuid4(), uuid.uuid4(), self.trace, b"p" * 32, 1, 1,
        )
        self.preflight = FakePreflight(ProviderTestPreflightSnapshot(self.claim, self.plan))
        envelope = SecretEnvelope(
            SecretRef(self.plan.secret_ref), SecretPurpose.AI_PROVIDER_KEY,
            SecretState.ACTIVE, SecretConsumer.AI_PROVIDER_ADAPTER, 1,
            b"cipher", b"metadata", "synthetic-only", self.claim.secret_version_id,
        )
        self.store = FakeStore(envelope)
        self.decryptor = FakeDecryptor()
        self.transport = FakeTransport()
        self.runner = ProviderProbeRunner(
            preflight=self.preflight,
            secrets=SecretResolver(self.store, self.decryptor, FakeAudit()),
            transport=self.transport,
        )

    def run_probe(self):
        return self.runner.run(job_id=self.claim.job_id, fencing_token=1,
                               worker_ref="probe-worker", trace_id=self.trace)

    def test_three_checkpoints_and_secret_zeroization(self):
        observed = self.run_probe()
        self.assertEqual((observed.job_id, observed.fencing_token, observed.outcome),
                         (self.claim.job_id, 1, "SUCCEEDED"))
        self.assertEqual(self.preflight.calls, 3)
        self.assertEqual(self.transport.connection.calls, 1)
        self.assertEqual(self.transport.connection.key, b"synthetic-key")
        self.assertEqual(self.decryptor.value, bytearray(len(self.decryptor.value)))

    def test_changed_facts_before_send_never_read_secret(self):
        self.preflight.next_result = ProviderTestPreflightSnapshot(
            replace(self.claim, secret_version_id=uuid.uuid4()), self.plan,
        )
        with self.assertRaises(ProviderProbeExecutionError) as caught:
            self.run_probe()
        self.assertEqual(caught.exception.code, "PROBE_FACTS_CHANGED")
        self.assertEqual(self.decryptor.calls, 0)
        self.assertEqual(self.transport.connection.calls, 0)

    def test_rotated_secret_rejected_before_send(self):
        self.store.envelope = replace(self.store.envelope, secret_version_id=uuid.uuid4())
        with self.assertRaises(ProviderProbeExecutionError) as caught:
            self.run_probe()
        self.assertEqual(caught.exception.code, "PROBE_SECRET_UNAVAILABLE")
        self.assertEqual(self.decryptor.calls, 0)
        self.assertEqual(self.transport.connection.calls, 0)

    def test_audit_scope_and_trace_bound_across_probe_then_cleared(self):
        scope = FakeAuditScope()
        self.runner._audit_scope = scope
        self.run_probe()
        self.assertEqual(scope.trace, None)
        self.assertEqual(self.transport.connection.trace, str(self.trace))
        self.assertIsNone(scope.bound)
        self.assertIsNone(current_trace_id())

    def test_audit_binding_failure_never_opens_transport(self):
        self.runner._audit_scope = FakeAuditScope(fail=True)
        with self.assertRaises(ProviderProbeExecutionError) as caught:
            self.run_probe()
        self.assertEqual(caught.exception.code, "PROBE_SECRET_UNAVAILABLE")
        self.assertEqual(self.transport.opened, 0)
        self.assertEqual(self.decryptor.calls, 0)


if __name__ == "__main__":
    unittest.main()
