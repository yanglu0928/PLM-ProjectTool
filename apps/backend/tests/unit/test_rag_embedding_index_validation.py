from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.rag.application.embedding_index_validation import (
    CompletedRAGEmbeddingIndexValidation,
    RAGEmbeddingIndexValidationError,
    RAGEmbeddingIndexValidationPolicy,
    RAGEmbeddingIndexValidationService,
)


def _facts():
    now = datetime(2026, 10, 4, 20, tzinfo=timezone.utc)
    job, build, index, actor, trace, validation = (
        uuid.uuid4() for _ in range(6)
    )
    claim = RAGIndexBuildClaim(
        job, build, index, "GLOBAL", None, actor, trace, 1, 1, 1,
        now, now + timedelta(minutes=2),
    )
    result = CompletedRAGEmbeddingIndexValidation(
        validation, index, build, "PASSED", "READY", 10000, now,
    )
    return claim, result


class _Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class _UOW:
    def __init__(self):
        self.transactions = []

    def __call__(self):
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


class _Claims:
    def __init__(self, claim):
        self.claim = claim

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.claim


class _Repository:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def validate_and_close(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.result


class RAGEmbeddingIndexValidationTests(unittest.TestCase):
    def setUp(self):
        self.claim, self.result = _facts()

    def service(self, result=None):
        uow = _UOW()
        repository = _Repository(self.result if result is None else result)
        service = RAGEmbeddingIndexValidationService(
            unit_of_work=uow, claims=_Claims(self.claim),
            repository=repository,
        )
        return service, uow, repository

    def test_pass_or_failed_outcome_commits_exact_claim(self):
        outcomes = (
            self.result,
            replace(self.result, validation_state="FAILED", index_state="FAILED",
                    observed_recall_basis_points=9000),
        )
        for outcome in outcomes:
            with self.subTest(state=outcome.validation_state):
                service, uow, repository = self.service(outcome)
                actual = service.validate(
                    job_id=self.claim.job_id, fencing_token=1,
                    worker_ref="rag-worker-a",
                )
                self.assertEqual(actual, outcome)
                self.assertTrue(uow.transactions[0].committed)
                self.assertEqual(repository.calls[0][1]["claim"], self.claim)

    def test_wrong_owner_result_rolls_back(self):
        service, uow, _ = self.service(replace(
            self.result, embedding_index_id=uuid.uuid4(),
        ))
        with self.assertRaises(RAGEmbeddingIndexValidationError):
            service.validate(
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-worker-a",
            )
        self.assertFalse(uow.transactions[0].committed)

    def test_policy_is_fixed_to_controlled_hnsw_settings(self):
        policy = RAGEmbeddingIndexValidationPolicy()
        self.assertEqual(policy.minimum_recall_basis_points, 9500)
        for change in (
            {"hnsw_ef_search": 100},
            {"hnsw_iterative_scan": "relaxed_order"},
            {"probe_limit": 0},
        ):
            with self.subTest(change=change), self.assertRaises(
                    RAGEmbeddingIndexValidationError):
                replace(policy, **change)


if __name__ == "__main__":
    unittest.main()
