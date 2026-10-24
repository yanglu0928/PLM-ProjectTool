from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.ai.application.publish_task_failure import (
    AITaskFailurePhase,
    AITaskFailurePublicationError,
    AITaskFailurePublisher,
    PublishedAITaskFailure,
)
from plm_assistant.modules.ai.application.complete_provider_failure import (
    AITaskProviderFailureService,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendError,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from unit.test_ai_suggestion_success import _Actor, _Audit, _Uow
from unit.test_ai_task_provider_send_service import _facts


class _Jobs:
    def __init__(self, *, fail=False, state="FAILED"):
        self.fail, self.state, self.calls = fail, state, []

    def retry_or_fail(self, transaction, **values):
        self.calls.append((transaction, values))
        if self.fail:
            raise JobLeaseError("STALE_LEASE")
        return self.state


class _Store:
    def __init__(self, result):
        self.result, self.calls = result, []

    def publish(self, transaction, **values):
        self.calls.append((transaction, values))
        return self.result


class AITaskFailureTests(unittest.TestCase):
    def setUp(self):
        self.now, self.prepared, self.begun, _ = _facts()

    def _publisher(
        self, *, jobs=None, audit=None,
        phase=AITaskFailurePhase.PROVIDER_OUTCOME_UNKNOWN,
        error_code="AI_PROVIDER_OUTCOME_UNKNOWN", retryable=False,
    ):
        uow = _Uow()
        result = PublishedAITaskFailure(
            error_code, retryable, phase, self.now,
        )
        store = _Store(result)
        return (
            AITaskFailurePublisher(
                unit_of_work=uow, store=store, jobs=jobs or _Jobs(),
                audit=audit or _Audit(), system_actor=_Actor(),
            ), uow, store,
        )

    def test_unknown_is_forced_non_retryable_and_job_never_auto_retries(self):
        jobs = _Jobs()
        publisher, uow, store = self._publisher(jobs=jobs)
        result = publisher.publish(
            prepared=self.prepared, begun=self.begun,
            worker_ref="worker-a",
            phase=AITaskFailurePhase.PROVIDER_OUTCOME_UNKNOWN,
            error_code="AI_PROVIDER_NETWORK_UNAVAILABLE", retryable=True,
        )
        self.assertFalse(result.retryable)
        self.assertTrue(uow.transactions[0].committed)
        self.assertEqual(jobs.calls[0][1]["retryable"], False)
        self.assertEqual(jobs.calls[0][1]["delay_seconds"], 0)
        self.assertEqual(
            jobs.calls[0][1]["error_code"], "AI_PROVIDER_OUTCOME_UNKNOWN",
        )
        self.assertEqual(
            store.calls[0][1]["error_code"], "AI_PROVIDER_OUTCOME_UNKNOWN",
        )

    def test_response_invalid_requires_fingerprint_and_is_not_retryable(self):
        publisher, uow, store = self._publisher(
            phase=AITaskFailurePhase.RESPONSE_INVALID,
            error_code="AI_PROVIDER_RESPONSE_INVALID",
        )
        with self.assertRaises(AITaskFailurePublicationError):
            publisher.publish(
                prepared=self.prepared, begun=self.begun,
                worker_ref="worker-a",
                phase=AITaskFailurePhase.RESPONSE_INVALID,
                error_code="AI_PROVIDER_RESPONSE_INVALID", retryable=False,
            )
        self.assertEqual(uow.transactions, [])
        publisher.publish(
            prepared=self.prepared, begun=self.begun,
            worker_ref="worker-a",
            phase=AITaskFailurePhase.RESPONSE_INVALID,
            error_code="AI_PROVIDER_RESPONSE_INVALID", retryable=False,
            response_fingerprint=b"r" * 32,
        )
        self.assertEqual(
            store.calls[0][1]["phase"], AITaskFailurePhase.RESPONSE_INVALID,
        )

    def test_lease_or_audit_failure_never_commits(self):
        for jobs, audit, code in (
            (_Jobs(fail=True), _Audit(), "AI_TASK_JOB_LEASE_LOST"),
            (_Jobs(), _Audit(fail=True), "AI_TASK_FAILURE_NOT_PUBLISHED"),
        ):
            publisher, uow, _ = self._publisher(
                jobs=jobs, audit=audit,
                phase=AITaskFailurePhase.PRE_SEND,
                error_code="AI_PROVIDER_SECRET_UNAVAILABLE",
                retryable=True,
            )
            with self.subTest(code=code), self.assertRaises(
                    AITaskFailurePublicationError) as caught:
                publisher.publish(
                    prepared=self.prepared, begun=self.begun,
                    worker_ref="worker-a",
                    phase=AITaskFailurePhase.PRE_SEND,
                    error_code="AI_PROVIDER_SECRET_UNAVAILABLE",
                    retryable=True,
                )
            self.assertEqual(caught.exception.code, code)
            self.assertFalse(uow.transactions[0].committed)

    def test_send_failure_phase_is_derived_from_durable_fence_boundary(self):
        publisher, _, store = self._publisher()
        service = AITaskProviderFailureService(publisher=publisher)
        service.complete(
            prepared=self.prepared, begun=self.begun,
            error=AITaskProviderSendError(
                "AI_PROVIDER_NETWORK_UNAVAILABLE",
                provider_outcome_unknown=True,
            ), worker_ref="worker-a",
        )
        self.assertEqual(
            store.calls[0][1]["phase"],
            AITaskFailurePhase.PROVIDER_OUTCOME_UNKNOWN,
        )


if __name__ == "__main__":
    unittest.main()
