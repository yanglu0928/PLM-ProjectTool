from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.ai.application.provider_probe_worker import (
    ProviderProbeOneShotWorker, ProviderProbeWorkerError,
)
from plm_assistant.modules.ai.application.publish_provider_probe_failure import (
    ProviderProbeFailureError, ProviderProbeFailureOutcome,
)
from plm_assistant.modules.ai.application.publish_provider_probe_success import ProviderProbePublicationError
from plm_assistant.modules.ai.application.run_provider_probe import (
    ProviderProbeExecutionError, ProviderProbeObservation,
)
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class Claims:
    def __init__(self, claim):
        self.claim = claim
        self.calls = 0
        self.raise_error = False

    def claim_next(self, **kwargs):
        self.calls += 1
        if self.raise_error:
            raise JobLeaseError("STORE_DOWN")
        return self.claim


class Runner:
    def __init__(self, claim):
        self.claim = claim
        self.calls = 0
        self.error = None
        self.observation = None

    def run(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.observation or ProviderProbeObservation(
            self.claim.job_id, self.claim.fencing_token,
        )


class Success:
    def __init__(self):
        self.id = uuid.uuid4()
        self.calls = 0
        self.error = None

    def publish(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.id


class Failure:
    def __init__(self):
        self.calls = []
        self.outcome = ProviderProbeFailureOutcome("FAILED", uuid.uuid4())
        self.error = None

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.outcome


class ProviderProbeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), b"p" * 32, 1, 1,
        )
        self.claims = Claims(self.claim)
        self.runner = Runner(self.claim)
        self.success = Success()
        self.failure = Failure()
        self.worker = ProviderProbeOneShotWorker(
            claims=self.claims, runner=self.runner,
            success=self.success, failure=self.failure,
        )

    def run_once(self):
        return self.worker.run_once(worker_ref="synthetic-worker")

    def test_no_job_is_idle_without_probe_or_publication(self):
        self.claims.claim = None
        result = self.run_once()
        self.assertEqual((result.state, result.job_id), ("IDLE", None))
        self.assertEqual((self.claims.calls, self.runner.calls, self.success.calls), (1, 0, 0))
        self.assertFalse(self.failure.calls)

    def test_one_claim_one_probe_and_success_publication(self):
        result = self.run_once()
        self.assertEqual((result.state, result.job_id, result.result_id),
                         ("SUCCEEDED", self.claim.job_id, self.success.id))
        self.assertEqual((self.claims.calls, self.runner.calls, self.success.calls), (1, 1, 1))
        self.assertFalse(self.failure.calls)

    def test_probe_error_enters_failure_publisher_once(self):
        self.runner.error = ProviderProbeExecutionError("PROBE_NETWORK_UNAVAILABLE")
        self.failure.outcome = ProviderProbeFailureOutcome("RETRY_WAIT", None)
        result = self.run_once()
        self.assertEqual((result.state, result.result_id), ("RETRY_WAIT", None))
        self.assertEqual(len(self.failure.calls), 1)
        self.assertEqual(self.failure.calls[0]["error"].code, "PROBE_NETWORK_UNAVAILABLE")
        self.assertEqual(self.success.calls, 0)

    def test_unknown_runner_exception_is_sanitized(self):
        self.runner.error = RuntimeError("synthetic private detail")
        self.run_once()
        self.assertEqual(self.failure.calls[0]["error"].code, "PROBE_UNAVAILABLE")
        self.assertNotIn("private detail", repr(self.failure.calls))

    def test_foreign_observation_never_publishes_success(self):
        self.runner.observation = ProviderProbeObservation(uuid.uuid4(), 1)
        result = self.run_once()
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(self.success.calls, 0)
        self.assertEqual(self.failure.calls[0]["error"].code, "PROBE_FACTS_CHANGED")

    def test_success_publish_rejection_routes_to_failure(self):
        self.success.error = ProviderProbePublicationError("AI_PROVIDER_CONFIG_CHANGED")
        result = self.run_once()
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(self.failure.calls[0]["error"].code, "AI_PROVIDER_CONFIG_CHANGED")

    def test_failure_publication_error_never_reports_success(self):
        self.runner.error = ProviderProbeExecutionError("PROBE_HTTP_REJECTED")
        self.failure.error = ProviderProbeFailureError("JOB_LEASE_LOST")
        with self.assertRaises(ProviderProbeWorkerError) as caught:
            self.run_once()
        self.assertEqual(caught.exception.code, "JOB_LEASE_LOST")

    def test_claim_store_failure_does_not_probe(self):
        self.claims.raise_error = True
        with self.assertRaises(ProviderProbeWorkerError) as caught:
            self.run_once()
        self.assertEqual(caught.exception.code, "JOB_STORE_UNAVAILABLE")
        self.assertEqual(self.runner.calls, 0)


if __name__ == "__main__":
    unittest.main()
