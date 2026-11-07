from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.fail_generation import (
    OutputGenerationFailureFacts,
)
from plm_assistant.modules.output.application.retry_generation import (
    OUTPUT_RETRY_DELAY_SECONDS, OutputGenerationRetryError, OutputGenerationRetryOwner,
)


class Transaction:
    def __init__(self) -> None:
        self.committed = False
    def commit(self) -> None:
        self.committed = True


class World:
    def __init__(self, job_state="RETRY_WAIT") -> None:
        self.request_id, self.project_id, self.job_id, self.snapshot_id = (
            uuid.uuid4() for _ in range(4))
        self.requester, self.system, self.trace = (uuid.uuid4() for _ in range(3))
        self.execution = uuid.uuid5(self.job_id, "output-generation:4")
        self.claim = ClaimedJob(
            self.job_id, "OUTPUT_GENERATE", "PROJECT", self.project_id,
            {"output_request_id": str(self.request_id),
             "context_snapshot_id": str(self.snapshot_id)},
            str(self.trace), 4, 2)
        self.state = {"output": "GENERATING", "job": "RUNNING", "lease": "ACTIVE",
                      "lock": 3, "execution": self.execution, "audit": []}
        self.expected_job_state = job_state
        self.fail_audit = False

    @contextmanager
    def uow(self):
        tx = Transaction()
        saved = {**self.state, "audit": list(self.state["audit"])}
        try:
            yield tx
        except Exception:
            self.state.clear()
            self.state.update(saved)
            raise

    def facts(self, changed):
        return OutputGenerationFailureFacts(
            self.request_id, self.project_id, self.job_id, self.snapshot_id,
            self.requester, self.execution, self.state["output"],
            self.state["lock"], changed)

    def lock_candidate(self, transaction, *, claim, execution_id):
        if self.state["output"] != "GENERATING" or execution_id != self.execution:
            raise RuntimeError("wrong candidate")
        return self.facts(False)

    def transition_retry(self, transaction, *, claim, execution_id,
                         expected_lock_version, target_state):
        if self.state["lock"] != expected_lock_version or execution_id != self.execution:
            raise RuntimeError("stale output")
        self.state["output"] = target_state
        self.state["lock"] += 1
        if target_state == "QUEUED":
            self.state["execution"] = None
        return self.facts(True)

    def check_output_claim(self, transaction, *, job_id, fencing_token, worker_ref):
        if (self.state["lease"] != "ACTIVE" or worker_ref != "worker"
                or job_id != self.claim.job_id or fencing_token != self.claim.fencing_token):
            raise JobLeaseError("STALE_LEASE")
        return self.claim

    def retry_or_fail(self, transaction, *, job_id, fencing_token, worker_ref,
                      error_code, retryable, delay_seconds):
        if (retryable is not True or delay_seconds != OUTPUT_RETRY_DELAY_SECONDS
                or error_code not in {"OUTPUT_GENERATION_TRANSIENT",
                                      "OUTPUT_PLUGIN_BUSY",
                                      "OUTPUT_STORAGE_TEMPORARY"}):
            raise AssertionError("retry policy was not fixed by the Owner")
        self.state["job"] = self.expected_job_state
        self.state["lease"] = "RELEASED"
        return self.expected_job_state


class Audit:
    def __init__(self, world):
        self.world = world
    def append(self, transaction, event: AuditEventDraft):
        if self.world.fail_audit:
            raise RuntimeError("synthetic audit failure")
        self.world.state["audit"].append(event)
        return uuid.uuid4()


class OutputGenerationRetryOwnerTests(unittest.TestCase):
    def make_owner(self, world):
        return OutputGenerationRetryOwner(
            unit_of_work=world.uow, jobs=world, repository=world,
            audit=Audit(world), system_actor_id=world.system)

    def test_transient_failure_requeues_output_and_job_atomically(self):
        world = World("RETRY_WAIT")
        result = self.make_owner(world).retry(
            world.claim, worker_ref="worker",
            error_code="OUTPUT_GENERATION_TRANSIENT")
        self.assertEqual(result.job_state, "RETRY_WAIT")
        self.assertEqual(result.retry_delay_seconds, 30)
        self.assertEqual(result.facts.state, "QUEUED")
        self.assertEqual(world.state["output"], "QUEUED")
        self.assertEqual(world.state["job"], "RETRY_WAIT")
        self.assertEqual(world.state["lease"], "RELEASED")
        self.assertIsNone(world.state["execution"])
        self.assertEqual(world.state["lock"], 4)
        event = world.state["audit"][0]
        self.assertEqual((event.action, event.outcome, event.after_state),
                         ("OUTPUT_GENERATION_RETRY_SCHEDULED", "SUCCESS", "QUEUED"))

    def test_attempt_exhaustion_fails_output_and_job(self):
        world = World("FAILED")
        result = self.make_owner(world).retry(
            world.claim, worker_ref="worker", error_code="OUTPUT_PLUGIN_BUSY")
        self.assertEqual(result.job_state, "FAILED")
        self.assertEqual(result.retry_delay_seconds, 0)
        self.assertEqual((world.state["output"], world.state["job"], world.state["lease"]),
                         ("FAILED", "FAILED", "RELEASED"))
        event = world.state["audit"][0]
        self.assertEqual((event.action, event.outcome, event.after_state),
                         ("OUTPUT_GENERATION_RETRY_EXHAUSTED", "FAILED", "FAILED"))

    def test_unlisted_error_code_rejected(self):
        world = World()
        with self.assertRaises(OutputGenerationRetryError):
            self.make_owner(world).retry(
                world.claim, worker_ref="worker", error_code="private stack trace")
        self.assertEqual(world.state["output"], "GENERATING")
        self.assertEqual(world.state["job"], "RUNNING")

    def test_wrong_worker_or_stale_token_rejected(self):
        world = World()
        owner = self.make_owner(world)
        with self.assertRaises(OutputGenerationRetryError):
            owner.retry(world.claim, worker_ref="intruder",
                        error_code="OUTPUT_STORAGE_TEMPORARY")
        stale = ClaimedJob(
            world.claim.job_id, world.claim.job_type, world.claim.scope,
            world.claim.project_id, world.claim.payload_refs, world.claim.trace_id,
            world.claim.fencing_token - 1, world.claim.attempt_no)
        with self.assertRaises(OutputGenerationRetryError):
            owner.retry(stale, worker_ref="worker",
                        error_code="OUTPUT_STORAGE_TEMPORARY")
        self.assertEqual(world.state["output"], "GENERATING")
        self.assertEqual(world.state["job"], "RUNNING")
        self.assertEqual(world.state["audit"], [])

    def test_audit_failure_rolls_back_retry_state(self):
        world = World()
        world.fail_audit = True
        with self.assertRaises(OutputGenerationRetryError):
            self.make_owner(world).retry(
                world.claim, worker_ref="worker",
                error_code="OUTPUT_GENERATION_TRANSIENT")
        self.assertEqual(world.state["output"], "GENERATING")
        self.assertEqual(world.state["job"], "RUNNING")
        self.assertEqual(world.state["lease"], "ACTIVE")
        self.assertEqual(world.state["lock"], 3)
        self.assertEqual(world.state["audit"], [])


if __name__ == "__main__":
    unittest.main()
