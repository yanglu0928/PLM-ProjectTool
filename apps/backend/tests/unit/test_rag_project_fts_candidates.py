from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    PreparedRAGRetrieval,
    RAGRetrievalPreparationError,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidate,
    ProjectFTSCandidatePlanner,
)


class _Repository:
    def __init__(self, candidates):
        self.candidates = candidates

    def project_fts(self, transaction, *, prepared):
        del transaction, prepared
        return self.candidates


class ProjectFTSCandidateTests(unittest.TestCase):
    def setUp(self):
        self.index, self.model = uuid.uuid4(), uuid.uuid4()
        self.prepared = PreparedRAGRetrieval(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            self.index, self.model, {"source_type": ["PROJECT_RECORD"]},
            "fts.project.v1", 5, b"a" * 32, b"q" * 32,
            bytearray(b"PLM query"),
        )

    def candidate(self, ordinal=0, **changes):
        values = dict(
            candidate_ordinal=ordinal, embedding_index_id=self.index,
            embedding_model_ref=self.model, chunk_id=uuid.uuid4(),
            document_version_ref=uuid.uuid4(), parse_result_ref=uuid.uuid4(),
            source_type="PROJECT_RECORD",
            source_locator={"locator_type": "PARSED_NODE"},
            retrieval_channel="FTS", raw_score_micros=100,
            authorization_snapshot_fingerprint=b"a" * 32,
        )
        values.update(changes)
        return ProjectFTSCandidate(**values)

    def test_bounded_plan_preserves_safe_candidate_refs(self):
        candidates = (self.candidate(0), self.candidate(1))
        plan = ProjectFTSCandidatePlanner(_Repository(candidates)).plan(
            object(), prepared=self.prepared,
        )
        self.assertEqual(plan.candidates, candidates)
        self.assertEqual(plan.project_index_ref, self.index)

    def test_cross_index_model_or_authorization_is_closed(self):
        for candidate in (
            self.candidate(embedding_index_id=uuid.uuid4()),
            self.candidate(embedding_model_ref=uuid.uuid4()),
            self.candidate(authorization_snapshot_fingerprint=b"x" * 32),
        ):
            with self.subTest(candidate=candidate), self.assertRaises(
                    RAGRetrievalPreparationError):
                ProjectFTSCandidatePlanner(_Repository((candidate,))).plan(
                    object(), prepared=self.prepared,
                )

    def test_duplicate_or_non_contiguous_candidates_are_closed(self):
        first = self.candidate(0)
        for candidates in (
            (self.candidate(1),),
            (first, self.candidate(1, chunk_id=first.chunk_id)),
        ):
            with self.subTest(candidates=candidates), self.assertRaises(
                    RAGRetrievalPreparationError):
                ProjectFTSCandidatePlanner(_Repository(candidates)).plan(
                    object(), prepared=self.prepared,
                )


if __name__ == "__main__":
    unittest.main()
