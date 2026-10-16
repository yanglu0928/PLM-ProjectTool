from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.ai.application.business_task_worker import (
    AIBusinessTaskOneShotWorker,
    AIBusinessTaskWorkerError,
)
from plm_assistant.modules.ai.application.complete_provider_failure import (
    AITaskProviderFailureError,
)
from plm_assistant.modules.ai.application.complete_provider_success import (
    AITaskProviderSuccessError,
)
from plm_assistant.modules.ai.application.publish_pre_begin_failure import (
    AITaskPreBeginFailureError,
    PublishedAITaskPreBeginFailure,
)
from plm_assistant.modules.ai.application.publish_suggestion_success import (
    PublishedAITaskSuggestion,
)
from plm_assistant.modules.ai.application.publish_task_failure import (
    AITaskFailurePhase,
    PublishedAITaskFailure,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendError,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    AITaskInvocationBeginError,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    AITaskInvocationPrepareError,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from unit.test_ai_provider_response_parser import _response
from unit.test_ai_task_provider_send_service import _facts


class _Stage:
    def __init__(self, events, name, result):
        self.events, self.name, self.result = events, name, result
        self.error = None
        self.calls = []

    def _call(self, values):
        self.events.append(self.name)
        self.calls.append(values)
        if self.error is not None:
            raise self.error
        return self.result


class _Leases(_Stage):
    def claim_next_ai_task(self, **values):
        return self._call(values)


class _Preparer(_Stage):
    def prepare(self, **values):
        return self._call(values)


class _Beginner(_Stage):
    def begin(self, **values):
        return self._call(values)


class _Sender(_Stage):
    def send_once(self, **values):
        return self._call(values)


class _Success(_Stage):
    def complete(self, **values):
        return self._call(values)


class _Failure(_Stage):
    def complete(self, **values):
        return self._call(values)


class _PreBegin(_Stage):
    def publish(self, **values):
        return self._call(values)


class AIBusinessTaskOneShotWorkerTests(unittest.TestCase):
    def setUp(self):
        self.now, self.prepared, self.begun, _ = _facts()
        grant = self.prepared.grant
        self.claim = ClaimedJob(
            grant.job_id, "AI_TASK_EXECUTE", "PROJECT", grant.project_id,
            {
                "ai_task_id": str(grant.ai_task_id),
                "egress_authorization_ref": str(grant.authorization_ref),
                "input_fingerprint": grant.source_refs_fingerprint.hex(),
            },
            str(grant.trace_id), grant.fencing_token, grant.attempt_no,
        )
        self.response = _response()
        self.suggestion = PublishedAITaskSuggestion(uuid.uuid4(), self.now)
        self.task_failure = PublishedAITaskFailure(
            "AI_PROVIDER_OUTCOME_UNKNOWN", False,
            AITaskFailurePhase.PROVIDER_OUTCOME_UNKNOWN, self.now,
        )
        self.pre_begin_result = PublishedAITaskPreBeginFailure(
            grant.ai_task_id, grant.job_id, grant.project_id,
            grant.requested_by, grant.trace_id,
            "AI_TASK_INVOCATION_NOT_PREPARED", True, self.now,
        )
        self.events = []
        self.leases = _Leases(self.events, "claim", self.claim)
        self.preparer = _Preparer(self.events, "prepare", self.prepared)
        self.beginner = _Beginner(self.events, "begin", self.begun)
        self.sender = _Sender(self.events, "send", self.response)
        self.success = _Success(self.events, "success", self.suggestion)
        self.failure = _Failure(self.events, "failure", self.task_failure)
        self.pre_begin = _PreBegin(
            self.events, "pre-begin-failure", self.pre_begin_result,
        )

    def worker(self, *, clock=None):
        return AIBusinessTaskOneShotWorker(
            leases=self.leases, preparer=self.preparer,
            beginner=self.beginner, sender=self.sender,
            success=self.success, failure=self.failure,
            pre_begin_failure=self.pre_begin,
            clock=clock or (lambda: self.now),
        )

    def execute(self, *, clock=None):
        return self.worker(clock=clock).run_once(worker_ref="ai-business-1")

    def assert_response_closed(self):
        with self.assertRaises(Exception):
            self.response.view()

    def test_idle_does_not_prepare_or_send(self):
        self.leases.result = None
        result = self.execute()
        self.assertEqual(result.state, "IDLE")
        self.assertEqual(self.events, ["claim"])
        self.assertEqual(self.leases.calls[0]["lease_seconds"], 300)

    def test_success_runs_exact_order_and_closes_response(self):
        result = self.execute()
        self.assertEqual(
            (result.state, result.job_id, result.result_id),
            ("SUCCEEDED", self.claim.job_id,
             self.suggestion.suggestion_payload_id),
        )
        self.assertEqual(
            self.events, ["claim", "prepare", "begin", "send", "success"],
        )
        self.assert_response_closed()

    def test_prepare_failure_closes_without_begin(self):
        self.preparer.error = AITaskInvocationPrepareError()
        result = self.execute()
        self.assertEqual(
            (result.state, result.error_code),
            ("FAILED", "AI_TASK_INVOCATION_NOT_PREPARED"),
        )
        self.assertEqual(self.events, ["claim", "prepare", "pre-begin-failure"])
        self.assertTrue(self.pre_begin.calls[0]["retryable"])

    def test_unknown_prepare_failure_is_sanitized(self):
        self.preparer.error = RuntimeError("private source content")
        self.pre_begin.result = PublishedAITaskPreBeginFailure(
            self.prepared.grant.ai_task_id, self.claim.job_id,
            self.prepared.grant.project_id, self.prepared.grant.requested_by,
            self.prepared.grant.trace_id, "AI_TASK_PREPARATION_FAILED", True,
            self.now,
        )
        result = self.execute()
        self.assertEqual(result.error_code, "AI_TASK_PREPARATION_FAILED")
        self.assertNotIn("private source content", repr(self.pre_begin.calls))

    def test_uncommitted_begin_failure_uses_pre_begin_closer(self):
        self.beginner.error = AITaskInvocationBeginError()
        self.pre_begin.result = PublishedAITaskPreBeginFailure(
            self.prepared.grant.ai_task_id, self.claim.job_id,
            self.prepared.grant.project_id, self.prepared.grant.requested_by,
            self.prepared.grant.trace_id, "AI_TASK_INVOCATION_NOT_STARTED", True,
            self.now,
        )
        result = self.execute()
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(
            self.events, ["claim", "prepare", "begin", "pre-begin-failure"],
        )

    def test_committed_begin_failure_is_left_for_reconciliation(self):
        self.beginner.error = AITaskInvocationBeginError(committed=True)
        result = self.execute()
        self.assertEqual(
            (result.state, result.error_code),
            ("RECONCILIATION_PENDING", "AI_TASK_INVOCATION_NOT_STARTED"),
        )
        self.assertEqual(self.events, ["claim", "prepare", "begin"])

    def test_send_failure_is_terminalized_once(self):
        self.sender.error = AITaskProviderSendError(
            "AI_PROVIDER_NETWORK_UNAVAILABLE", provider_outcome_unknown=True,
        )
        result = self.execute()
        self.assertEqual(
            (result.state, result.error_code),
            ("FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN"),
        )
        self.assertEqual(
            self.events, ["claim", "prepare", "begin", "send", "failure"],
        )
        self.assertIs(self.failure.calls[0]["error"], self.sender.error)

    def test_unknown_send_exception_is_conservatively_unknown(self):
        self.sender.error = RuntimeError("private transport detail")
        self.execute()
        error = self.failure.calls[0]["error"]
        self.assertEqual(error.code, "AI_PROVIDER_OUTCOME_UNKNOWN")
        self.assertTrue(error.provider_outcome_unknown)
        self.assertNotIn("private transport detail", repr(self.failure.calls))

    def test_failure_publication_error_never_reports_terminal_state(self):
        self.sender.error = AITaskProviderSendError()
        self.failure.error = AITaskProviderFailureError(
            "AI_TASK_FAILURE_NOT_PUBLISHED",
        )
        with self.assertRaises(AIBusinessTaskWorkerError) as caught:
            self.execute()
        self.assertEqual(caught.exception.code, "AI_TASK_FAILURE_NOT_PUBLISHED")

    def test_invalid_response_terminal_result_is_reported_failed(self):
        self.success.error = AITaskProviderSuccessError(
            "AI_PROVIDER_RESPONSE_INVALID",
        )
        result = self.execute()
        self.assertEqual(
            (result.state, result.error_code),
            ("FAILED", "AI_PROVIDER_RESPONSE_INVALID"),
        )
        self.assert_response_closed()

    def test_result_publication_failure_waits_for_reconciliation(self):
        self.success.error = AITaskProviderSuccessError(
            "AI_TASK_RESULT_NOT_PUBLISHED",
        )
        result = self.execute()
        self.assertEqual(
            (result.state, result.error_code),
            ("RECONCILIATION_PENDING", "AI_TASK_RESULT_NOT_PUBLISHED"),
        )
        self.assert_response_closed()

    def test_claim_failure_stops_and_clock_failure_closes_before_send(self):
        self.leases.error = JobLeaseError("STORE_DOWN")
        with self.assertRaises(AIBusinessTaskWorkerError) as caught:
            self.execute()
        self.assertEqual(caught.exception.code, "JOB_STORE_UNAVAILABLE")

        self.leases.error = None
        self.pre_begin.result = PublishedAITaskPreBeginFailure(
            self.prepared.grant.ai_task_id, self.claim.job_id,
            self.prepared.grant.project_id, self.prepared.grant.requested_by,
            self.prepared.grant.trace_id, "AI_TASK_PREPARATION_FAILED", True,
            self.now,
        )
        result = self.execute(clock=lambda: object())
        self.assertEqual(
            (result.state, result.error_code),
            ("FAILED", "AI_TASK_PREPARATION_FAILED"),
        )
        self.assertEqual(self.events, ["claim", "claim", "pre-begin-failure"])

    def test_pre_begin_publication_failure_poison_cycle(self):
        self.preparer.error = AITaskInvocationPrepareError()
        self.pre_begin.error = AITaskPreBeginFailureError(
            "AI_TASK_JOB_LEASE_LOST",
        )
        with self.assertRaises(AIBusinessTaskWorkerError) as caught:
            self.execute()
        self.assertEqual(caught.exception.code, "AI_TASK_JOB_LEASE_LOST")


if __name__ == "__main__":
    unittest.main()
