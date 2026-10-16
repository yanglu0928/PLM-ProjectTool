from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.retrieval_metrics import top_k_recall  # noqa: E402


class RetrievalMetricsTests(unittest.TestCase):
    def test_top_k_recall_is_one_for_complete_top_five(self) -> None:
        expected = ["A", "B", "C", "D", "E"]
        self.assertEqual(1.0, top_k_recall(expected, expected, k=5))

    def test_top_k_recall_ignores_results_after_k(self) -> None:
        self.assertEqual(0.5, top_k_recall(["A", "B"], ["A", "X", "B"], k=2))

    def test_top_k_recall_rejects_empty_expected_set(self) -> None:
        with self.assertRaises(ValueError):
            top_k_recall([], ["A"], k=5)


if __name__ == "__main__":
    unittest.main()
