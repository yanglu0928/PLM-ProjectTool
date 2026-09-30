from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from poc03_rag.holdout_independence import assess_independence  # noqa: E402


def case(index: int) -> dict:
    return {
        "case_id": f"HO-{index:04d}",
        "query": f"Synthetic question {index}",
        "expected_relevant_chunk_ids": [f"chunk-{index}"],
        "content_sha256": f"{index:064x}",
        "expected_citations": [{"document_id": "synthetic", "chunk_id": f"chunk-{index}", "source_locator": f"p/{index}"}],
    }


class IndependenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = {"cases": [case(index) for index in range(100, 150)]}
        self.prior = {"cases": [case(index) for index in range(50)]}

    def test_disjoint_synthetic_set_passes_without_raw_values(self) -> None:
        result = assess_independence(self.candidate, [self.prior])
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("Synthetic question", str(result))
        self.assertEqual(result["prior_case_count"], 50)

    def test_each_exposure_channel_fails(self) -> None:
        for field in ("query", "expected_relevant_chunk_ids", "content_sha256", "expected_citations"):
            with self.subTest(field=field):
                candidate = {"cases": [dict(item) for item in self.candidate["cases"]]}
                candidate["cases"][0][field] = self.prior["cases"][0][field]
                self.assertEqual(assess_independence(candidate, [self.prior])["status"], "FAIL")

    def test_missing_history_and_incomplete_candidate_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "prior"):
            assess_independence(self.candidate, [])
        candidate = {"cases": [dict(item) for item in self.candidate["cases"]]}
        candidate["cases"][0].pop("query")
        self.assertEqual(assess_independence(candidate, [self.prior])["status"], "FAIL")

    def test_internal_duplicate_query_fails(self) -> None:
        candidate = {"cases": [dict(item) for item in self.candidate["cases"]]}
        candidate["cases"][1]["query"] = "  SYNTHETIC   question 100  "
        result = assess_independence(candidate, [self.prior])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["candidate_duplicate_counts"]["query"], 1)

    def test_case_ids_may_restart_in_new_dataset(self) -> None:
        candidate = {"cases": [dict(item) for item in self.candidate["cases"]]}
        for index, item in enumerate(candidate["cases"]):
            item["case_id"] = f"HO-{index:04d}"
        self.assertEqual(assess_independence(candidate, [self.prior])["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
