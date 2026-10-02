from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from plm_assistant.modules.ai.application.probe_policy import ProviderProbePlan
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.provider_test_preflight import (
    ProviderTestPreflightError, ProviderTestPreflightSnapshot,
)
from plm_assistant.modules.ai.application.publish_provider_probe_success import (
    ProviderProbePublicationError, ProviderProbeSuccessPublisher,
)
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeObservation
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class Transaction:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, kind, *_):
        if kind is not None or not self.committed:
            self.rolled_back = True

    def commit(self):
        self.committed = True


class Preflight:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0
        self.failure = None

    def check_locked(self, tx, **_):
        self.calls += 1
        if self.failure:
            raise ProviderTestPreflightError(self.failure)
        return self.snapshot


class Store:
    def __init__(self):
        self.calls = 0
        self.failure = False
        self.id = uuid.uuid4()

    def append_success(self, tx, *, snapshot):
        self.calls += 1
        if self.failure:
            raise RuntimeError("synthetic persistence failure")
        return self.id


class Jobs:
    def __init__(self, claim):
        self.claim = claim
        self.calls = 0
        self.failure = False

    def finish(self, tx, **_):
        self.calls += 1
        if self.failure:
            raise JobLeaseError("STALE_LEASE")
        return SimpleNamespace(job_id=self.claim.job_id,
                               fencing_token=self.claim.fencing_token,
                               attempt_no=self.claim.attempt_no,
                               job_type="AI_PROVIDER_TEST")


class Actor:
    def __init__(self):
        self.identity = uuid.uuid4()

    def assert_current(self):
        return self.identity


class Audit:
    def __init__(self):
        self.events = []
        self.failure = False

    def append(self, tx, event):
        if self.failure:
            raise RuntimeError("synthetic audit failure")
        self.events.append(event)
        return uuid.uuid4()


class ProviderProbeSuccessTests(unittest.TestCase):
    def setUp(self):
        self.trace = uuid.uuid4()
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
            uuid.uuid4(), uuid.uuid4(), self.trace, b"a" * 32, 1, 1,
        )
        self.snapshot = ProviderTestPreflightSnapshot(
            self.claim, ProviderProbePlan(
                self.claim.provider_id, 1, "trusted.synthetic",
                "https://probe.example.test/v1/chat", "synthetic-chat",
                uuid.uuid4(),
            ),
        )
        self.tx = Transaction()
        self.preflight = Preflight(self.snapshot)
        self.store = Store()
        self.jobs = Jobs(self.claim)
        self.actor = Actor()
        self.audit = Audit()
        self.publisher = ProviderProbeSuccessPublisher(
            unit_of_work=lambda: self.tx, preflight=self.preflight,
            store=self.store, jobs=self.jobs,
            audit=ProviderProbeAudit(system_actor=self.actor, audit=self.audit),
        )
        self.observation = ProviderProbeObservation(self.claim.job_id, 1)

    def publish(self):
        return self.publisher.publish(observation=self.observation,
                                      worker_ref="synthetic-worker", trace_id=self.trace)

    def test_success_is_one_transaction_in_order(self):
        self.assertEqual(self.publish(), self.store.id)
        self.assertEqual((self.preflight.calls, self.store.calls, self.jobs.calls), (1, 1, 1))
        self.assertTrue(self.tx.committed)
        self.assertFalse(self.tx.rolled_back)
        self.assertEqual(self.audit.events[0].action, "AI_PROVIDER_TEST_SUCCEEDED")

    def test_changed_facts_never_append_or_finish(self):
        self.preflight.failure = "AI_PROVIDER_CONFIG_CHANGED"
        with self.assertRaises(ProviderProbePublicationError) as caught:
            self.publish()
        self.assertEqual(caught.exception.code, "AI_PROVIDER_CONFIG_CHANGED")
        self.assertEqual((self.store.calls, self.jobs.calls), (0, 0))
        self.assertTrue(self.tx.rolled_back)

    def test_store_or_finish_failure_rolls_back(self):
        for which in ("store", "jobs"):
            with self.subTest(which=which):
                self.setUp()
                setattr(getattr(self, which), "failure", True)
                with self.assertRaises(ProviderProbePublicationError):
                    self.publish()
                self.assertFalse(self.tx.committed)
                self.assertTrue(self.tx.rolled_back)

    def test_audit_failure_rolls_back_success(self):
        self.audit.failure = True
        with self.assertRaises(ProviderProbePublicationError):
            self.publish()
        self.assertFalse(self.tx.committed)
        self.assertTrue(self.tx.rolled_back)

    def test_rejects_foreign_observation_before_transaction(self):
        with self.assertRaises(ProviderProbePublicationError):
            self.publisher.publish(observation=object(), worker_ref="synthetic-worker",
                                   trace_id=self.trace)
        self.assertEqual(self.preflight.calls, 0)


if __name__ == "__main__":
    unittest.main()
