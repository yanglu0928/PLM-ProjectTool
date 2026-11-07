from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.fail_generation import OutputGenerationFailureFacts
from plm_assistant.modules.output.application.retry_generation import (
    OutputGenerationRetryResult,
)
from plm_assistant.modules.plugin.application.execution_failure import (
    PluginExecutionFailureFacts,
)
from plm_assistant.modules.plugin.application.execution_retry import (
    PluginExecutionRetryError,
    PluginExecutionRetryOwner,
)


class _Uow:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rollbacks += 1
        return False

    def commit(self):
        self.commits += 1


class _OutputRetry:
    def __init__(self, job_state="RETRY_WAIT"):
        self.job_state = job_state
        self.calls = []

    def retry_in_transaction(self, transaction, claim, *, worker_ref, error_code):
        self.calls.append((transaction, claim, worker_ref, error_code))
        output = OutputGenerationFailureFacts(
            output_request_id=uuid.UUID(claim.payload_refs["output_request_id"]),
            project_id=claim.project_id,
            job_id=claim.job_id,
            context_snapshot_id=uuid.UUID(claim.payload_refs["context_snapshot_id"]),
            requested_by=uuid.uuid4(),
            execution_id=uuid.uuid5(claim.job_id, "output-generation:" + str(claim.fencing_token)),
            state="QUEUED" if self.job_state == "RETRY_WAIT" else "FAILED",
            lock_version=2,
            changed=True,
        )
        return OutputGenerationRetryResult(
            output, self.job_state, 30 if self.job_state == "RETRY_WAIT" else 0,
        )


class _Repository:
    def __init__(self, claim):
        self.claim = claim
        self.rows = []
        self.authorized = 0
        self.events = []

    def lock_running(self, transaction, *, claim):
        self.rows.append(("lock", transaction))
        return PluginExecutionFailureFacts(
            plugin_execution_id=uuid.uuid4(), project_id=claim.project_id,
            job_id=claim.job_id,
            output_request_id=uuid.UUID(claim.payload_refs["output_request_id"]),
            output_context_snapshot_id=uuid.UUID(claim.payload_refs["context_snapshot_id"]),
            attempt_no=claim.attempt_no, trace_id=uuid.UUID(claim.trace_id),
            execution_state="RUNNING", lock_version=1, changed=False,
        )

    def authorize_owner_writes(self, transaction):
        self.authorized += 1

    def fail_retryable(self, transaction, *, claim, plugin_execution_id,
                       expected_lock_version, error_code):
        self.rows.append(("fail", transaction, error_code))
        return PluginExecutionFailureFacts(
            plugin_execution_id=plugin_execution_id, project_id=claim.project_id,
            job_id=claim.job_id,
            output_request_id=uuid.UUID(claim.payload_refs["output_request_id"]),
            output_context_snapshot_id=uuid.UUID(claim.payload_refs["context_snapshot_id"]),
            attempt_no=claim.attempt_no, trace_id=uuid.UUID(claim.trace_id),
            execution_state="FAILED", lock_version=expected_lock_version + 1,
            changed=True,
        )

    def append_failed_event(self, transaction, **kwargs):
        self.events.append((transaction, kwargs))


class _Audit:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def append(self, transaction, event):
        self.events.append((transaction, event))
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        return uuid.uuid4()


def _claim(attempt_no=1):
    job_id, project_id, request_id, context_id, trace_id = (uuid.uuid4() for _ in range(5))
    return ClaimedJob(
        job_id=job_id, job_type="OUTPUT_GENERATE", scope="PROJECT",
        project_id=project_id,
        payload_refs={"output_request_id": str(request_id),
                      "context_snapshot_id": str(context_id)},
        trace_id=str(trace_id), fencing_token=11, attempt_no=attempt_no,
    )


class PluginExecutionRetryOwnerTests(unittest.TestCase):
    def create(self, claim, *, output_state="RETRY_WAIT", audit=None):
        uow = _Uow()
        output = _OutputRetry(output_state)
        repository = _Repository(claim)
        audit = audit or _Audit()
        owner = PluginExecutionRetryOwner(
            unit_of_work=lambda: uow, output_retry=output,
            repository=repository, audit=audit,
        )
        return owner, uow, output, repository, audit

    def test_retry_schedules_output_job_and_plugin_atomically(self):
        claim = _claim()
        owner, uow, output, repository, audit = self.create(claim)
        result = owner.retry(claim, worker_ref="worker-1", error_code="OUTPUT_PLUGIN_BUSY")
        self.assertEqual(result.job_state, "RETRY_WAIT")
        self.assertEqual(result.output_state, "QUEUED")
        self.assertEqual(result.retry_delay_seconds, 30)
        self.assertEqual(result.facts.execution_state, "FAILED")
        self.assertEqual(output.calls[0][0], uow)
        self.assertEqual(repository.rows[0][1], uow)
        self.assertEqual(repository.rows[1][1], uow)
        self.assertEqual(repository.authorized, 1)
        self.assertEqual(repository.events[0][0], uow)
        self.assertEqual(audit.events[0][0], uow)
        self.assertIs(type(audit.events[0][1]), AuditEventDraft)
        self.assertEqual(audit.events[0][1].action, "PLUGIN_EXECUTION_RETRY_SCHEDULED")
        self.assertEqual(uow.commits, 1)
        self.assertEqual(uow.rollbacks, 0)

    def test_exhausted_job_and_output_fail_closed_with_retryable_error_history(self):
        claim = _claim(attempt_no=2)
        owner, _uow, _output, _repository, audit = self.create(
            claim, output_state="FAILED",
        )
        result = owner.retry(claim, worker_ref="worker-1", error_code="OUTPUT_PLUGIN_BUSY")
        self.assertEqual(result.job_state, "FAILED")
        self.assertEqual(result.output_state, "FAILED")
        self.assertEqual(result.retry_delay_seconds, 0)
        self.assertEqual(audit.events[0][1].action, "PLUGIN_EXECUTION_RETRY_EXHAUSTED")
        self.assertEqual(audit.events[0][1].outcome, "FAILED")

    def test_plugin_audit_failure_rolls_back_shared_transaction(self):
        claim = _claim()
        audit = _Audit(fail=True)
        owner, uow, _output, repository, _audit = self.create(claim, audit=audit)
        with self.assertRaises(PluginExecutionRetryError):
            owner.retry(claim, worker_ref="worker-1", error_code="OUTPUT_PLUGIN_BUSY")
        self.assertEqual(uow.commits, 0)
        self.assertEqual(uow.rollbacks, 1)
        self.assertEqual(len(repository.events), 1)

    def test_unknown_error_and_bad_worker_rejected_before_writes(self):
        claim = _claim()
        owner, uow, output, repository, audit = self.create(claim)
        for worker, code in (("worker-1", "OUTPUT_PLUGIN_UNAVAILABLE"),
                             ("invalid worker", "OUTPUT_PLUGIN_BUSY")):
            with self.assertRaises(PluginExecutionRetryError):
                owner.retry(claim, worker_ref=worker, error_code=code)
        self.assertEqual(output.calls, [])
        self.assertEqual(repository.rows, [])
        self.assertEqual(audit.events, [])
        self.assertEqual(uow.commits, 0)


if __name__ == "__main__":
    unittest.main()
