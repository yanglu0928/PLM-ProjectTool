from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager

from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, JobLeaseService,
)


class FakeRepository:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def check_output_claim(self, transaction, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        self.commits += 1


class TestOutputJobLeaseProof(unittest.TestCase):
    def setUp(self):
        self.claim = ClaimedJob(
            job_id=uuid.uuid4(), job_type="OUTPUT_GENERATE", scope="PROJECT",
            project_id=uuid.uuid4(),
            payload_refs={"output_request_id": str(uuid.uuid4()),
                          "context_snapshot_id": str(uuid.uuid4())},
            trace_id=str(uuid.uuid4()), fencing_token=3, attempt_no=2,
        )
        self.repository = FakeRepository(result=self.claim)
        self.uow = FakeUnitOfWork()
        self.service = JobLeaseService(
            unit_of_work=lambda: self.uow, repository=self.repository,
        )

    def test_current_output_lease_proof_commits_short_read_transaction(self):
        proof = self.service.check_output_claim(
            job_id=self.claim.job_id, fencing_token=3,
            worker_ref="output-worker-1",
        )
        self.assertEqual(proof, self.claim)
        self.assertEqual(self.uow.commits, 1)
        self.assertEqual(self.repository.calls[0]["fencing_token"], 3)

    def test_invalid_job_and_fencing_are_rejected_before_repository(self):
        for kwargs, code in (
            ({"job_id": uuid.UUID(int=0), "fencing_token": 3,
              "worker_ref": "output-worker-1"}, "INVALID_JOB_ID"),
            ({"job_id": self.claim.job_id, "fencing_token": True,
              "worker_ref": "output-worker-1"}, "INVALID_FENCING_TOKEN"),
        ):
            with self.subTest(code=code):
                repository = FakeRepository(result=self.claim)
                service = JobLeaseService(
                    unit_of_work=lambda: self.uow, repository=repository,
                )
                with self.assertRaises(JobLeaseError) as raised:
                    service.check_output_claim(**kwargs)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(repository.calls, [])

    def test_repository_stale_lease_failure_propagates_without_commit(self):
        repository = FakeRepository(error=JobLeaseError("STALE_LEASE"))
        uow = FakeUnitOfWork()
        service = JobLeaseService(unit_of_work=lambda: uow, repository=repository)
        with self.assertRaises(JobLeaseError) as raised:
            service.check_output_claim(
                job_id=self.claim.job_id, fencing_token=3,
                worker_ref="output-worker-1",
            )
        self.assertEqual(raised.exception.code, "STALE_LEASE")
        self.assertEqual(uow.commits, 0)

    def test_inconsistent_repository_result_fails_closed(self):
        repository = FakeRepository(result=None)
        uow = FakeUnitOfWork()
        service = JobLeaseService(unit_of_work=lambda: uow, repository=repository)
        with self.assertRaises(JobLeaseError) as raised:
            service.check_output_claim(
                job_id=self.claim.job_id, fencing_token=3,
                worker_ref="output-worker-1",
            )
        self.assertEqual(raised.exception.code, "INCONSISTENT_LEASE")
        self.assertEqual(uow.commits, 0)


if __name__ == "__main__":
    unittest.main()
