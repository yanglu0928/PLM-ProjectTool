from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureError, OutputGenerationFailureFacts,
    OutputGenerationFailureOwner,
)


class FakeTransaction:
    def __init__(self, state: dict) -> None:
        self.state = state
        self.committed = False

    def commit(self) -> None:
        self.committed = True


class FakeWorld:
    def __init__(self) -> None:
        self.request_id, self.project_id, self.job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.snapshot_id, self.requester_id, self.system_id, self.trace_id = (
            uuid.uuid4() for _ in range(4))
        self.claim = ClaimedJob(
            self.job_id, "OUTPUT_GENERATE", "PROJECT", self.project_id,
            {"output_request_id": str(self.request_id),
             "context_snapshot_id": str(self.snapshot_id)},
            str(self.trace_id), 7, 2,
        )
        self.execution_id = uuid.uuid5(self.job_id, "output-generation:7")
        self.state = {"output": "GENERATING", "job": "RUNNING", "lock": 1,
                      "lease": "ACTIVE", "audit": []}
        self.fail_audit = False
        self.calls = 0

    @contextmanager
    def unit_of_work(self):
        tx = FakeTransaction(self.state)
        saved = {**self.state, "audit": list(self.state["audit"])}
        try:
            yield tx
        except Exception:
            self.state.clear()
            self.state.update(saved)
            raise

    def facts(self, *, changed: bool) -> OutputGenerationFailureFacts:
        return OutputGenerationFailureFacts(
            self.request_id, self.project_id, self.job_id, self.snapshot_id,
            self.requester_id, self.execution_id, self.state["output"],
            self.state["lock"], changed,
        )

    def lock_candidate(self, transaction, *, claim, execution_id):
        if (claim.job_id != self.job_id or execution_id != self.execution_id
                or self.state["output"] != "GENERATING"):
            raise OutputGenerationFailureError()
        return self.facts(changed=False)

    def fail_generation(self, transaction, *, claim, execution_id, expected_lock_version):
        if (execution_id != self.execution_id or self.state["lock"] != expected_lock_version
                or self.state["output"] != "GENERATING"):
            raise OutputGenerationFailureError()
        self.state["output"] = "FAILED"
        self.state["lock"] += 1
        self.calls += 1
        return self.facts(changed=True)

    def check_output_claim(self, transaction, *, job_id, fencing_token, worker_ref):
        if (job_id != self.claim.job_id or fencing_token != self.claim.fencing_token
                or worker_ref != "worker-1" or self.state["lease"] != "ACTIVE"):
            raise JobLeaseError("STALE_LEASE")
        return self.claim

    def retry_or_fail(self, transaction, *, job_id, fencing_token, worker_ref,
                      error_code, retryable, delay_seconds):
        if (retryable is not False or delay_seconds != 0
                or error_code not in {"OUTPUT_GENERATION_FAILED",
                                      "OUTPUT_PLUGIN_UNAVAILABLE",
                                      "OUTPUT_VALIDATION_FAILED"}):
            raise AssertionError("unsafe Job failure policy")
        self.state["job"] = "FAILED"
        self.state["lease"] = "RELEASED"
        return "FAILED"


class FakeAudit:
    def __init__(self, world: FakeWorld) -> None:
        self.world = world

    def append(self, transaction, event: AuditEventDraft):
        if self.world.fail_audit:
            raise RuntimeError("synthetic audit failure")
        self.world.state["audit"].append(event)
        return uuid.uuid4()


class OutputGenerationFailureOwnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = FakeWorld()
        self.owner = self.make_owner()

    def make_owner(self):
        return OutputGenerationFailureOwner(
            unit_of_work=self.world.unit_of_work,
            jobs=self.world,
            repository=self.world,
            audit=FakeAudit(self.world),
            system_actor_id=self.world.system_id,
        )

    def test_terminal_failure_updates_output_job_and_system_audit(self):
        result = self.owner.fail(self.world.claim, worker_ref="worker-1",
                                 error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual((result.state, result.lock_version, result.changed),
                         ("FAILED", 2, True))
        self.assertEqual((self.world.state["job"], self.world.state["lease"]),
                         ("FAILED", "RELEASED"))
        event = self.world.state["audit"][0]
        self.assertEqual((event.action, event.outcome, event.before_state, event.after_state),
                         ("OUTPUT_GENERATION_FAILED", "FAILED", "GENERATING", "FAILED"))
        self.assertEqual((event.actor_id, event.original_actor_id),
                         (self.world.system_id, self.world.requester_id))

    def test_unlisted_error_code_is_rejected_before_transaction(self):
        with self.assertRaises(OutputGenerationFailureError):
            self.owner.fail(self.world.claim, worker_ref="worker-1",
                            error_code="secret stack trace")
        self.assertEqual(self.world.calls, 0)
        self.assertEqual(self.world.state["job"], "RUNNING")

    def test_wrong_worker_is_rejected_without_changes(self):
        with self.assertRaises(OutputGenerationFailureError):
            self.owner.fail(self.world.claim, worker_ref="worker-2",
                            error_code="OUTPUT_PLUGIN_UNAVAILABLE")
        self.assertEqual(self.world.state["output"], "GENERATING")
        self.assertEqual(self.world.state["job"], "RUNNING")
        self.assertEqual(self.world.state["audit"], [])

    def test_stale_fencing_token_is_rejected_without_changes(self):
        stale = ClaimedJob(
            self.world.claim.job_id, self.world.claim.job_type, self.world.claim.scope,
            self.world.claim.project_id, self.world.claim.payload_refs,
            self.world.claim.trace_id, self.world.claim.fencing_token - 1,
            self.world.claim.attempt_no,
        )
        with self.assertRaises(OutputGenerationFailureError):
            self.owner.fail(stale, worker_ref="worker-1",
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual(self.world.state["output"], "GENERATING")
        self.assertEqual(self.world.state["job"], "RUNNING")

    def test_audit_failure_rolls_back_job_and_output(self):
        self.world.fail_audit = True
        with self.assertRaises(OutputGenerationFailureError):
            self.owner.fail(self.world.claim, worker_ref="worker-1",
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual(self.world.state["output"], "GENERATING")
        self.assertEqual(self.world.state["job"], "RUNNING")
        self.assertEqual(self.world.state["lease"], "ACTIVE")
        self.assertEqual(self.world.state["audit"], [])

    def test_non_output_job_rejected(self):
        other = ClaimedJob(
            self.world.claim.job_id, "DOCUMENT_PARSE", self.world.claim.scope,
            self.world.claim.project_id, self.world.claim.payload_refs,
            self.world.claim.trace_id, self.world.claim.fencing_token,
            self.world.claim.attempt_no,
        )
        with self.assertRaises(OutputGenerationFailureError):
            self.owner.fail(other, worker_ref="worker-1",
                            error_code="OUTPUT_GENERATION_FAILED")
        self.assertEqual(self.world.state["output"], "GENERATING")


if __name__ == "__main__":
    unittest.main()
