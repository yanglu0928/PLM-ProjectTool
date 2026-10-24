from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import RAGIndexBuildClaim
from plm_assistant.modules.rag.application.embedding_batch_send_fence import (
    RAGEmbeddingBatchPayloadProof,
    RAGEmbeddingBatchSendFenceError,
    RAGEmbeddingBatchSendFenceService,
    RAGEmbeddingBatchSendMaterial,
)


class _Transaction:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.fail_commit = fail_commit
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.committed = True


class _Claims:
    def __init__(self, claim, *, fail: bool = False) -> None:
        self.claim = claim
        self.fail = fail

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        if self.fail:
            raise JobLeaseError("STALE_LEASE")
        return self.claim


class _Repository:
    def __init__(self, material=None, *, fail: bool = False) -> None:
        self.material = material
        self.fail = fail
        self.seen = None

    def mark_running(self, transaction, **kwargs):
        del transaction
        if self.fail:
            raise RuntimeError("private database error")
        self.seen = kwargs
        return self.material


class RAGEmbeddingBatchSendFenceTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 10, 4, 13, tzinfo=timezone.utc)
        self.claim = RAGIndexBuildClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "PROJECT", uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), 1, 1, 1, now,
            now + timedelta(minutes=2),
        )
        self.proof = RAGEmbeddingBatchPayloadProof(
            self.claim.embedding_build_id, self.claim.embedding_index_id,
            1, 1, 2, b"s" * 32, b"p" * 32, 128, 32,
        )
        self.material = RAGEmbeddingBatchSendMaterial(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), "OPENAI_COMPATIBLE", "BAILIAN_V1",
            "cn-beijing", "CUSTOMER_CONTENT", "text-embedding-v4",
            "PROVIDER_MANAGED", 1024, now + timedelta(minutes=10), 1,
        )

    def test_fence_commits_current_batch_before_return(self) -> None:
        transaction = _Transaction()
        repository = _Repository(self.material)
        result = RAGEmbeddingBatchSendFenceService(
            unit_of_work=lambda: transaction,
            claims=_Claims(self.claim), repository=repository,
        ).fence(
            proof=self.proof, job_id=self.claim.job_id,
            fencing_token=1, worker_ref="rag-worker-01",
        )
        self.assertTrue(transaction.committed)
        self.assertEqual(result.fenced_at, self.claim.observed_at)
        self.assertEqual(result.material.lock_version, 1)
        self.assertIs(repository.seen["proof"], self.proof)

    def test_identity_mismatch_fails_before_repository(self) -> None:
        repository = _Repository(self.material)
        with self.assertRaises(RAGEmbeddingBatchSendFenceError):
            RAGEmbeddingBatchSendFenceService(
                unit_of_work=_Transaction, claims=_Claims(self.claim),
                repository=repository,
            ).fence(
                proof=replace(self.proof, embedding_index_id=uuid.uuid4()),
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-worker-01",
            )
        self.assertIsNone(repository.seen)

    def test_stale_claim_repository_and_commit_fail_closed(self) -> None:
        for claims, repository, transaction in (
            (_Claims(self.claim, fail=True), _Repository(self.material), _Transaction()),
            (_Claims(self.claim), _Repository(None), _Transaction()),
            (_Claims(self.claim), _Repository(self.material, fail=True), _Transaction()),
            (_Claims(self.claim), _Repository(self.material), _Transaction(fail_commit=True)),
        ):
            with self.subTest(claims=claims, repository=repository), \
                    self.assertRaises(RAGEmbeddingBatchSendFenceError) as raised:
                RAGEmbeddingBatchSendFenceService(
                    unit_of_work=lambda transaction=transaction: transaction,
                    claims=claims, repository=repository,
                ).fence(
                    proof=self.proof, job_id=self.claim.job_id,
                    fencing_token=1, worker_ref="rag-worker-01",
                )
            self.assertFalse(raised.exception.committed)


if __name__ == "__main__":
    unittest.main()
