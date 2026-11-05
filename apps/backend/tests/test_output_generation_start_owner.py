from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace

from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.output.application.start_generation import (
    OutputGenerationStartError, OutputGenerationStartFacts, OutputGenerationStartOwner,
)


class FakeTransaction:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True


class FakeUnitOfWork(AbstractContextManager[FakeTransaction]):
    def __init__(self) -> None:
        self.transaction = FakeTransaction()

    def __enter__(self) -> FakeTransaction:
        return self.transaction

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None and not self.transaction.committed:
            self.transaction.rolled_back = True
        return False


class FakeJobs:
    def __init__(self, claim: ClaimedJob) -> None:
        self.claim = claim
        self.error: Exception | None = None

    def check_output_claim(self, transaction, *, job_id, fencing_token, worker_ref):
        if self.error:
            raise self.error
        if (job_id != self.claim.job_id or fencing_token != self.claim.fencing_token
                or worker_ref != "worker-01"):
            raise JobLeaseError("STALE_LEASE")
        return self.claim


class FakeRepository:
    def __init__(self, claim: ClaimedJob, *, state: str = "QUEUED") -> None:
        self.claim = claim
        self.state = state
        self.calls: list[str] = []

    def lock_candidate(self, transaction, *, claim, execution_id):
        self.calls.append("lock")
        if claim.payload_refs != self.claim.payload_refs:
            raise OutputGenerationStartError()
        return OutputGenerationStartFacts(
            uuid.UUID(claim.payload_refs["output_request_id"]), claim.project_id,
            claim.job_id, uuid.UUID(claim.payload_refs["context_snapshot_id"]),
            REQUESTER, "DOCX", execution_id, self.state, 4, False,
        )

    def start_generation(self, transaction, *, claim, execution_id, expected_lock_version):
        self.calls.append("start")
        self.state = "GENERATING"
        return OutputGenerationStartFacts(
            uuid.UUID(claim.payload_refs["output_request_id"]), claim.project_id,
            claim.job_id, uuid.UUID(claim.payload_refs["context_snapshot_id"]),
            REQUESTER, "DOCX", execution_id, "GENERATING",
            expected_lock_version + 1, True,
        )


class FakeAudit:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events = []

    def append(self, transaction, event):
        if self.fail:
            raise RuntimeError("injected audit failure")
        self.events.append(event)
        return uuid.uuid4()


PROJECT = uuid.uuid4()
JOB = uuid.uuid4()
REQUEST = uuid.uuid4()
SNAPSHOT = uuid.uuid4()
TRACE = uuid.uuid4()
REQUESTER = uuid.uuid4()
SYSTEM_ACTOR = uuid.uuid4()
CLAIM = ClaimedJob(
    job_id=JOB, job_type="OUTPUT_GENERATE", scope="PROJECT", project_id=PROJECT,
    payload_refs={"output_request_id": str(REQUEST),
                  "context_snapshot_id": str(SNAPSHOT)},
    trace_id=str(TRACE), fencing_token=3, attempt_no=2,
)


class OutputGenerationStartOwnerTests(unittest.TestCase):
    def build(self, *, state="QUEUED", audit=None, jobs=None):
        self.uow = FakeUnitOfWork()
        self.repo = FakeRepository(CLAIM, state=state)
        self.audit = audit or FakeAudit()
        self.jobs = jobs or FakeJobs(CLAIM)
        owner = OutputGenerationStartOwner(
            unit_of_work=lambda: self.uow, jobs=self.jobs, repository=self.repo,
            audit=self.audit, system_actor_id=SYSTEM_ACTOR,
        )
        return owner

    def test_start_commits_state_and_system_audit_with_requester_attribution(self):
        owner = self.build()
        result = owner.start(CLAIM, worker_ref="worker-01")
        self.assertEqual(result.state, "GENERATING")
        self.assertTrue(result.changed)
        self.assertTrue(self.uow.transaction.committed)
        self.assertFalse(self.uow.transaction.rolled_back)
        self.assertEqual(self.repo.calls, ["lock", "start"])
        self.assertEqual(len(self.audit.events), 1)
        event = self.audit.events[0]
        self.assertEqual(event.actor_type, "SYSTEM")
        self.assertEqual(event.actor_id, SYSTEM_ACTOR)
        self.assertEqual(event.original_actor_id, REQUESTER)
        self.assertEqual(event.before_state, "QUEUED")
        self.assertEqual(event.after_state, "GENERATING")

    def test_lease_rejection_rolls_back_candidate_lock_without_audit(self):
        jobs = FakeJobs(CLAIM)
        jobs.error = JobLeaseError("STALE_LEASE")
        owner = self.build(jobs=jobs)
        with self.assertRaises(OutputGenerationStartError):
            owner.start(CLAIM, worker_ref="worker-01")
        self.assertEqual(self.repo.calls, ["lock"])
        self.assertFalse(self.uow.transaction.committed)
        self.assertTrue(self.uow.transaction.rolled_back)
        self.assertEqual(self.audit.events, [])

    def test_audit_failure_rolls_back_generation_transition(self):
        owner = self.build(audit=FakeAudit(fail=True))
        with self.assertRaises(OutputGenerationStartError):
            owner.start(CLAIM, worker_ref="worker-01")
        self.assertFalse(self.uow.transaction.committed)
        self.assertTrue(self.uow.transaction.rolled_back)

    def test_exact_execution_replay_skips_second_audit(self):
        owner = self.build(state="GENERATING")
        result = owner.start(CLAIM, worker_ref="worker-01")
        self.assertEqual(result.state, "GENERATING")
        self.assertFalse(result.changed)
        self.assertTrue(self.uow.transaction.committed)
        self.assertEqual(self.repo.calls, ["lock"])
        self.assertEqual(self.audit.events, [])

    def test_wrong_worker_fails_closed_before_state_update(self):
        owner = self.build()
        with self.assertRaises(OutputGenerationStartError):
            owner.start(CLAIM, worker_ref="worker-02")
        self.assertEqual(self.repo.calls, ["lock"])
        self.assertFalse(self.uow.transaction.committed)
        self.assertTrue(self.uow.transaction.rolled_back)


if __name__ == "__main__":
    unittest.main()
