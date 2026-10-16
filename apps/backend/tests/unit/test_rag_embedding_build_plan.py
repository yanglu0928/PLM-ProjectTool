from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.rag.application.embedding_build_plan import (
    PlannedRAGEmbeddingBuild,
    RAGEmbeddingBatchPlan,
    RAGEmbeddingBuildPlanError,
    RAGEmbeddingBuildPlanner,
    RAGEmbeddingBuildPlanRequest,
)


class _Transaction:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def commit(self): self.committed = True


class _Repository:
    def __init__(self, *, fail: bool = False, wrong: bool = False) -> None:
        self.fail, self.wrong = fail, wrong

    def create(self, transaction, *, request, embedding_build_id, job_id):
        del transaction
        if self.fail:
            raise RuntimeError("private database detail")
        return PlannedRAGEmbeddingBuild(
            uuid.uuid4() if self.wrong else embedding_build_id,
            request.embedding_index_id,
            job_id,
        )


class RAGEmbeddingBuildPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.batch = RAGEmbeddingBatchPlan(
            1, 1, 2, b"s" * 32, b"p" * 32, 100, 20, uuid.uuid4(),
        )
        self.request = RAGEmbeddingBuildPlanRequest(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), (self.batch,),
        )

    def test_plan_is_created_and_committed(self) -> None:
        transaction = _Transaction()
        result = RAGEmbeddingBuildPlanner(
            unit_of_work=lambda: transaction, repository=_Repository(),
        ).create(self.request)
        self.assertTrue(transaction.committed)
        self.assertEqual(result.embedding_index_id, self.request.embedding_index_id)
        self.assertEqual(result.build_generation, 1)

    def test_batch_partition_and_authorizations_are_strict(self) -> None:
        for batches in (
            (),
            (replace(self.batch, batch_ordinal=2),),
            (replace(self.batch, source_first_ordinal=2),),
            (self.batch, replace(
                self.batch, batch_ordinal=2, source_first_ordinal=3,
            )),
        ):
            with self.subTest(batches=batches), self.assertRaises(RAGEmbeddingBuildPlanError):
                RAGEmbeddingBuildPlanRequest(
                    self.request.embedding_index_id, self.request.actor_id,
                    self.request.trace_id, batches,
                )

    def test_repository_failure_or_wrong_identity_is_hidden(self) -> None:
        for repository in (_Repository(fail=True), _Repository(wrong=True)):
            with self.subTest(repository=repository), self.assertRaisesRegex(
                    RAGEmbeddingBuildPlanError, "RAG_INDEX_BUILD_NOT_PLANNED"):
                RAGEmbeddingBuildPlanner(
                    unit_of_work=lambda: _Transaction(), repository=repository,
                ).create(self.request)


if __name__ == "__main__":
    unittest.main()
