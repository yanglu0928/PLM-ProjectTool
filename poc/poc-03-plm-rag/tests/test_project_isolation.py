from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.project_isolation import (  # noqa: E402
    FULL_TEXT_SQL,
    HYBRID_SQL,
    VECTOR_SQL,
    ProjectRetrievalRequest,
    ProjectScopeError,
    assert_project_isolated,
)


class ProjectIsolationTests(unittest.TestCase):
    def test_project_id_is_required(self) -> None:
        with self.assertRaises(ProjectScopeError):
            ProjectRetrievalRequest(
                project_id=" ",
                query_text="query",
                query_vector=(1.0, 0.0),
            )

    def test_every_query_uses_parameterized_project_filter(self) -> None:
        for sql in (VECTOR_SQL, FULL_TEXT_SQL, HYBRID_SQL):
            self.assertIn("project_id = %(project_id)s", sql)
            self.assertNotIn("PROJECT-A", sql)

    def test_vector_query_uses_cosine_distance_and_top_k(self) -> None:
        self.assertIn("embedding <=> %(query_vector)s::vector", VECTOR_SQL)
        self.assertIn("LIMIT %(limit)s", VECTOR_SQL)

    def test_hybrid_query_uses_both_channels_and_fixed_weights(self) -> None:
        self.assertIn("vector_hits AS", HYBRID_SQL)
        self.assertIn("text_hits AS", HYBRID_SQL)
        self.assertIn("score * 0.6", HYBRID_SQL)
        self.assertIn("score * 0.4", HYBRID_SQL)
        self.assertIn("UNION ALL", HYBRID_SQL)
        self.assertIn("LIMIT %(candidate_limit)s", HYBRID_SQL)
        request = ProjectRetrievalRequest(
            project_id="PROJECT-A",
            query_text="query",
            query_vector=(1.0, 0.0),
            limit=5,
        )
        self.assertEqual(20, request.parameters["candidate_limit"])

    def test_parameters_keep_project_id_out_of_sql_text(self) -> None:
        request = ProjectRetrievalRequest(
            project_id="PROJECT-A' OR '1'='1",
            query_text="shared",
            query_vector=(1.0, 0.0),
        )
        self.assertEqual("PROJECT-A' OR '1'='1", request.parameters["project_id"])
        self.assertNotIn(str(request.parameters["project_id"]), VECTOR_SQL)

    def test_cross_project_rows_are_rejected(self) -> None:
        with self.assertRaises(ProjectScopeError):
            assert_project_isolated(
                [("A-1", "PROJECT-A"), ("B-1", "PROJECT-B")],
                "PROJECT-A",
            )

    def test_matching_rows_have_zero_leakage(self) -> None:
        self.assertEqual(
            0,
            assert_project_isolated(
                [("A-1", "PROJECT-A"), ("A-2", "PROJECT-A")],
                "PROJECT-A",
            ),
        )


if __name__ == "__main__":
    unittest.main()
