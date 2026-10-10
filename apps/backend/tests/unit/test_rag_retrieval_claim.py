from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_retrieval_claim import (
    RAGRetrievalClaim,
    RAGRetrievalClaims,
)


class _Transaction:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self) -> None:
        self.committed = True


class _Repository:
    def __init__(self, value=None, *, fail: bool = False) -> None:
        self.value = value
        self.fail = fail

    def claim_next(self, transaction, **kwargs):
        del transaction, kwargs
        if self.fail:
            raise RuntimeError("private database detail")
        return self.value

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        if self.fail:
            raise RuntimeError("private database detail")
        return self.value


class RAGRetrievalClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        self.claim = RAGRetrievalClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), 1, 1, now, now + timedelta(minutes=2),
        )

    def test_owner_scoped_claim_commits_exact_proof(self) -> None:
        tx = _Transaction()
        service = RAGRetrievalClaims(
            unit_of_work=lambda: tx, repository=_Repository(self.claim),
        )
        result = service.claim_next(worker_ref="rag-retrieval-01", lease_seconds=60)
        self.assertIs(result, self.claim)
        self.assertTrue(tx.committed)

    def test_current_claim_requires_exact_generation(self) -> None:
        service = RAGRetrievalClaims(
            unit_of_work=lambda: _Transaction(), repository=_Repository(self.claim),
        )
        self.assertIs(service.check_current(
            object(), job_id=self.claim.job_id, fencing_token=1,
            worker_ref="rag-retrieval-01",
        ), self.claim)
        for value in (replace(self.claim, job_id=uuid.uuid4()), None):
            with self.subTest(value=value), self.assertRaises(JobLeaseError):
                RAGRetrievalClaims(
                    unit_of_work=lambda: _Transaction(), repository=_Repository(value),
                ).check_current(
                    object(), job_id=self.claim.job_id, fencing_token=1,
                    worker_ref="rag-retrieval-01",
                )
        with self.assertRaises(JobLeaseError):
            service.check_current(
                object(), job_id=self.claim.job_id, fencing_token=2,
                worker_ref="rag-retrieval-01",
            )

    def test_shape_and_failures_are_closed(self) -> None:
        for changes in (
            {"fencing_token": 2}, {"attempt_no": 2},
            {"lease_expires_at": self.claim.observed_at},
            {"project_id": uuid.UUID(int=0)},
        ):
            with self.subTest(changes=changes), self.assertRaises(JobLeaseError):
                replace(self.claim, **changes)
        service = RAGRetrievalClaims(
            unit_of_work=lambda: _Transaction(), repository=_Repository(fail=True),
        )
        with self.assertRaisesRegex(JobLeaseError, "JOB_STORE_UNAVAILABLE"):
            service.claim_next(worker_ref="rag-retrieval-01", lease_seconds=60)
        for worker, seconds in (("bad worker", 60), ("worker", 2), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                service.claim_next(worker_ref=worker, lease_seconds=seconds)


if __name__ == "__main__":
    unittest.main()
