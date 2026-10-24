from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.infrastructure.rag_retrieval_claim_repository import (
    SqlAlchemyRAGRetrievalClaimRepository,
)


class RAGRetrievalClaimRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        self.run_id = uuid.uuid4()
        self.job = SimpleNamespace(
            job_id=uuid.uuid4(), owner_module="rag", job_type="RAG_RETRIEVAL",
            scope="PROJECT", project_id=uuid.uuid4(), actor_ref=uuid.uuid4(),
            trace_id=str(uuid.uuid4()),
            payload_refs={"retrieval_run_id": str(self.run_id)},
            idempotency_key=str(self.run_id), max_attempts=1, attempt_count=1,
            fencing_token=1, completed_at=None, state="RUNNING",
            lease_expires_at=self.now + timedelta(minutes=1),
        )
        self.repository = SqlAlchemyRAGRetrievalClaimRepository()

    def test_snapshot_requires_exact_retrieval_job_shape(self) -> None:
        claim = self.repository._snapshot(None, self.job, observed_at=self.now)
        self.assertEqual(claim.retrieval_run_id, self.run_id)
        generic = ClaimedJob(
            self.job.job_id, "RAG_RETRIEVAL", "PROJECT", self.job.project_id,
            dict(self.job.payload_refs), self.job.trace_id, 1, 1,
        )
        self.assertTrue(self.repository._matches_generic(claim, generic))

    def test_snapshot_rejects_payload_or_generation_drift(self) -> None:
        for field, value in (
            ("payload_refs", {
                "retrieval_run_id": str(self.run_id), "query": "must-not-exist",
            }),
            ("idempotency_key", str(uuid.uuid4())),
            ("max_attempts", 2),
            ("attempt_count", 2),
            ("fencing_token", 2),
            ("scope", "GLOBAL"),
            ("state", "PENDING"),
            ("lease_expires_at", self.now),
        ):
            with self.subTest(field=field):
                original = getattr(self.job, field)
                setattr(self.job, field, value)
                try:
                    with self.assertRaises(JobLeaseError):
                        self.repository._snapshot(None, self.job, observed_at=self.now)
                finally:
                    setattr(self.job, field, original)


if __name__ == "__main__":
    unittest.main()
