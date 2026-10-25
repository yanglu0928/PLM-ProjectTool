from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.publish_provider_probe_failure import (
    ProviderProbeFailureError, ProviderProbeFailurePublisher,
    classify_provider_probe_failure,
)
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeExecutionError
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class Transaction:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, kind, *_):
        if kind or not self.committed:
            self.rolled_back = True

    def commit(self):
        self.committed = True


class Claims:
    def __init__(self, claim):
        self.claim = claim
        self.stale = False

    def check_current(self, tx, **_):
        if self.stale:
            raise JobLeaseError("STALE_LEASE")
        return self.claim


class Jobs:
    def __init__(self):
        self.calls = []

    def retry_or_fail(self, tx, **kwargs):
        self.calls.append(kwargs)
        return "RETRY_WAIT" if kwargs["retryable"] else "FAILED"


class Results:
    def __init__(self):
        self.calls = []
        self.id = uuid.uuid4()

    def append_failure(self, tx, **kwargs):
        self.calls.append(kwargs)
        return self.id


class Actor:
    def __init__(self):
        self.id = uuid.uuid4()

    def assert_current(self):
        return self.id


class Audit:
    def __init__(self):
        self.events = []
        self.failure = False

    def append(self, tx, event):
        if self.failure:
            raise RuntimeError("synthetic audit failure")
        self.events.append(event)
        return uuid.uuid4()


class ProviderProbeFailureTests(unittest.TestCase):
    def setUp(self):
        self.trace = uuid.uuid4()
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
            uuid.uuid4(), uuid.uuid4(), self.trace, b"p" * 32, 1, 1,
        )
        self.tx = Transaction()
        self.claims = Claims(self.claim)
        self.jobs = Jobs()
        self.results = Results()
        self.audit = Audit()
        self.actor = Actor()
        self.publisher = ProviderProbeFailurePublisher(
            unit_of_work=lambda: self.tx, claims=self.claims,
            jobs=self.jobs, results=self.results,
            audit=ProviderProbeAudit(system_actor=self.actor, audit=self.audit),
        )

    def fail(self, error):
        return self.publisher.publish(
            job_id=self.claim.job_id, fencing_token=1,
            worker_ref="synthetic-worker", trace_id=self.trace,
            error=error,
        )

    def test_retry_has_attempt_and_audit_but_no_final_result(self):
        outcome = self.fail(ProviderProbeExecutionError("PROBE_NETWORK_UNAVAILABLE"))
        self.assertEqual((outcome.job_state, outcome.result_id), ("RETRY_WAIT", None))
        self.assertEqual(self.jobs.calls[0]["delay_seconds"], 5)
        self.assertFalse(self.results.calls)
        self.assertEqual(self.audit.events[0].reason_code, "PROBE_NETWORK_UNAVAILABLE")
        self.assertTrue(self.tx.committed)

    def test_last_attempt_and_fatal_are_terminal(self):
        for attempt, code in ((3, "PROBE_NETWORK_UNAVAILABLE"),
                              (1, "AI_PROVIDER_CONFIG_CHANGED")):
            with self.subTest(attempt=attempt):
                self.setUp()
                object.__setattr__(self.claim, "attempt_no", attempt)
                outcome = self.fail(ProviderProbeExecutionError(code))
                self.assertEqual((outcome.job_state, outcome.result_id),
                                 ("FAILED", self.results.id))
                self.assertEqual(self.results.calls[0]["failure_code"], code)
                self.assertEqual(self.audit.events[0].action, "AI_PROVIDER_TEST_FAILED")
                self.assertTrue(self.tx.committed)

    def test_unknown_exception_is_sanitized(self):
        self.fail(RuntimeError("secret text never recorded"))
        self.assertEqual(self.jobs.calls[0]["error_code"], "PROBE_UNAVAILABLE")
        self.assertNotIn("secret text", repr(self.audit.events))

    def test_stale_claim_and_audit_failure_rollback(self):
        self.claims.stale = True
        with self.assertRaises(ProviderProbeFailureError) as caught:
            self.fail(ProviderProbeExecutionError("PROBE_NETWORK_UNAVAILABLE"))
        self.assertEqual(caught.exception.code, "JOB_LEASE_LOST")
        self.assertFalse(self.jobs.calls)
        self.setUp()
        self.audit.failure = True
        with self.assertRaises(ProviderProbeFailureError):
            self.fail(ProviderProbeExecutionError("PROBE_HTTP_REJECTED"))
        self.assertTrue(self.tx.rolled_back)
        self.assertFalse(self.tx.committed)

    def test_job_lease_loss_is_never_published(self):
        with self.assertRaises(ProviderProbeFailureError) as caught:
            self.fail(ProviderProbeExecutionError("JOB_LEASE_LOST"))
        self.assertEqual(caught.exception.code, "JOB_LEASE_LOST")
        self.assertFalse(self.jobs.calls)
        self.assertTrue(self.tx.rolled_back)

    def test_classification_bounds(self):
        self.assertEqual(classify_provider_probe_failure(
            ProviderProbeExecutionError("PROBE_NETWORK_UNAVAILABLE"), attempt_no=2,
        ), ("PROBE_NETWORK_UNAVAILABLE", True, 15))
        with self.assertRaises(ProviderProbeFailureError):
            classify_provider_probe_failure(RuntimeError(), attempt_no=4)


if __name__ == "__main__":
    unittest.main()
