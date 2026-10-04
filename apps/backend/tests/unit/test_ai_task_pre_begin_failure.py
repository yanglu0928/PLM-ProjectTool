from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.publish_pre_begin_failure import (
    AITaskPreBeginFailureError,
    AITaskPreBeginFailurePublisher,
    PublishedAITaskPreBeginFailure,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from unit.test_ai_suggestion_success import _Audit, _Uow


class _Jobs:
    def __init__(self, state="FAILED"):
        self.state = state
        self.calls = []

    def retry_or_fail(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.state


class _Store:
    def __init__(self, result):
        self.result = result

    def publish(self, *_args, **_kwargs):
        return self.result


class _Actor:
    def __init__(self, value):
        self.value = value

    def assert_current(self):
        return self.value


class _MalformedAudit(_Audit):
    def append(self, transaction, event):
        self.events.append((transaction, event))
        return None


class AITaskPreBeginFailureTests(unittest.TestCase):
    def setUp(self):
        self.task, self.job, self.project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.requester, self.trace, self.system = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.claim = ClaimedJob(
            self.job, "AI_TASK_EXECUTE", "PROJECT", self.project,
            {"ai_task_id": str(self.task)}, str(self.trace), 2, 1,
        )
        self.result = PublishedAITaskPreBeginFailure(
            self.task, self.job, self.project, self.requester, self.trace,
            "AI_TASK_CONTENT_UNAVAILABLE", True, datetime.now(timezone.utc),
        )

    def service(self, *, audit=None, jobs=None):
        uow = _Uow()
        service = AITaskPreBeginFailurePublisher(
            unit_of_work=uow, store=_Store(self.result),
            jobs=jobs or _Jobs(), audit=audit or _Audit(),
            system_actor=_Actor(self.system),
        )
        return service, uow

    def test_closes_job_task_and_audits_without_invocation(self):
        audit = _Audit()
        jobs = _Jobs()
        service, uow = self.service(audit=audit, jobs=jobs)
        result = service.publish(
            claim=self.claim, worker_ref="ai-task-worker-1",
            error_code="AI_TASK_CONTENT_UNAVAILABLE", retryable=True,
        )
        self.assertEqual(result, self.result)
        self.assertTrue(uow.transactions[0].committed)
        self.assertFalse(jobs.calls[0][1]["retryable"])
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_PREPARATION_FAILED")
        self.assertEqual((event.before_state, event.after_state),
                         ("QUEUED", "FAILED"))
        self.assertIsNone(event.target_version_id)

    def test_non_failed_job_transition_rolls_back(self):
        service, uow = self.service(jobs=_Jobs("RETRY_WAIT"))
        with self.assertRaises(AITaskPreBeginFailureError):
            service.publish(
                claim=self.claim, worker_ref="ai-task-worker-1",
                error_code="AI_TASK_CONTENT_UNAVAILABLE", retryable=True,
            )
        self.assertFalse(uow.transactions[0].committed)

    def test_audit_failure_rolls_back(self):
        service, uow = self.service(audit=_Audit(fail=True))
        with self.assertRaises(AITaskPreBeginFailureError):
            service.publish(
                claim=self.claim, worker_ref="ai-task-worker-1",
                error_code="AI_TASK_CONTENT_UNAVAILABLE", retryable=True,
            )
        self.assertFalse(uow.transactions[0].committed)

    def test_malformed_audit_result_rolls_back(self):
        service, uow = self.service(audit=_MalformedAudit())
        with self.assertRaises(AITaskPreBeginFailureError):
            service.publish(
                claim=self.claim, worker_ref="ai-task-worker-1",
                error_code="AI_TASK_CONTENT_UNAVAILABLE", retryable=True,
            )
        self.assertFalse(uow.transactions[0].committed)


if __name__ == "__main__":
    unittest.main()
