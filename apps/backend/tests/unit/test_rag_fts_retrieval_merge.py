from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.rag.application.fts_retrieval_merge import (
    FTSRetrievalMergePlanner,
)
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalPreparationError,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidate,
    ProjectFTSCandidatePlan,
)


class FTSRetrievalMergeTests(unittest.TestCase):
    def setUp(self):
        self.run, self.project, self.index, self.model = (
            uuid.uuid4() for _ in range(4))
        self.planner = FTSRetrievalMergePlanner()

    def candidate(self, ordinal, score):
        return ProjectFTSCandidate(
            ordinal, self.index, self.model, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), "PROJECT_RECORD", {"locator_type": "PARSED_NODE"},
            "FTS", score, b"a" * 32,
        )

    def plan(self, items, top_k=2):
        source = ProjectFTSCandidatePlan(
            self.run, self.project, self.index, b"q" * 32, tuple(items),
        )
        return self.planner.plan(source, top_k=top_k)

    def test_stable_top_k_and_score_parts(self):
        result = self.plan((
            self.candidate(0, 20), self.candidate(1, 100), self.candidate(2, 50),
        ))
        self.assertEqual(
            [item.final_score_micros for item in result.candidates], [100, 50])
        self.assertEqual(result.quality_flags, ())
        self.assertFalse(result.degraded)
        self.assertEqual(result.rerank_state, "NOT_APPLICABLE")
        self.assertEqual(
            [part.score_kind for part in result.candidates[0].score_parts],
            ["FTS", "FINAL"],
        )

    def test_shortfall_is_explicit_but_not_degraded(self):
        result = self.plan((self.candidate(0, 20),), top_k=5)
        self.assertEqual(result.quality_flags, ("CANDIDATE_SHORTFALL",))
        self.assertFalse(result.degraded)

    def test_zero_candidates_fail_without_empty_context_semantics(self):
        with self.assertRaisesRegex(
                RAGRetrievalPreparationError, "RAG_NO_AUTHORIZED_CANDIDATES"):
            self.plan((), top_k=5)

    def test_tie_uses_existing_stable_ordinal(self):
        first, second = self.candidate(0, 100), self.candidate(1, 100)
        result = self.plan((first, second))
        self.assertEqual(
            [item.candidate.chunk_id for item in result.candidates],
            [first.chunk_id, second.chunk_id],
        )


if __name__ == "__main__":
    unittest.main()
