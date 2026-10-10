from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.rag_index_build_claim import RAGIndexBuildClaim
from plm_assistant.modules.rag.application.embedding_build_begin import (
    RAGEmbeddingBuildBeginError,
    RAGEmbeddingBuildBeginService,
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
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.seen = None

    def begin(self, transaction, *, claim):
        del transaction
        if self.fail:
            raise RuntimeError("private database error")
        self.seen = claim


class RAGEmbeddingBuildBeginTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 10, 4, 11, tzinfo=timezone.utc)
        self.claim = RAGIndexBuildClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "GLOBAL", None,
            uuid.uuid4(), uuid.uuid4(), 1, 1, 1, now,
            now + timedelta(minutes=2),
        )

    def test_current_claim_and_transitions_commit_together(self) -> None:
        tx = _Transaction()
        repository = _Repository()
        service = RAGEmbeddingBuildBeginService(
            unit_of_work=lambda: tx, claims=_Claims(self.claim),
            repository=repository,
        )
        result = service.begin(
            job_id=self.claim.job_id, fencing_token=1,
            worker_ref="rag-worker-01",
        )
        self.assertTrue(tx.committed)
        self.assertIs(repository.seen, self.claim)
        self.assertEqual(result.embedding_build_id, self.claim.embedding_build_id)

    def test_stale_claim_repository_and_commit_fail_closed(self) -> None:
        for claims, repository, transaction in (
            (_Claims(self.claim, fail=True), _Repository(), _Transaction()),
            (_Claims(self.claim), _Repository(fail=True), _Transaction()),
            (_Claims(self.claim), _Repository(), _Transaction(fail_commit=True)),
        ):
            with self.subTest(claims=claims, repository=repository), \
                    self.assertRaises(RAGEmbeddingBuildBeginError) as raised:
                RAGEmbeddingBuildBeginService(
                    unit_of_work=lambda transaction=transaction: transaction,
                    claims=claims, repository=repository,
                ).begin(
                    job_id=self.claim.job_id, fencing_token=1,
                    worker_ref="rag-worker-01",
                )
            self.assertFalse(raised.exception.committed)


if __name__ == "__main__":
    unittest.main()
