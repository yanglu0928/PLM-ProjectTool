from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.layered_diagnostics import (  # noqa: E402
    build_layered_diagnostic,
    expand_ranked_neighbors,
    fuse_ranked_scores,
    sanitized_layered_report,
)


class LayeredDiagnosticsTests(unittest.TestCase):
    def test_bottlenecks_and_classification_are_aggregated(self) -> None:
        cases = [
            {
                "case_id": "GD-0001",
                "source_type": "CONTRACT",
                "expected_relevant_chunk_ids": ["DOC-A-C-1"],
                "expected_classification": "STANDARD_SATISFIED",
            },
            {
                "case_id": "GD-0002",
                "source_type": "SURVEY",
                "expected_relevant_chunk_ids": ["DOC-B-C-2"],
                "expected_classification": "NO_RELIABLE_MATCH",
            },
        ]
        report = build_layered_diagnostic(
            cases,
            vector_rankings={"GD-0001": ["DOC-A-C-1"], "GD-0002": ["OTHER-C-1"]},
            full_text_rankings={"GD-0001": [], "GD-0002": ["OTHER-C-2"]},
            fusion_rankings={"GD-0001": ["DOC-A-C-1"], "GD-0002": ["OTHER-C-1"]},
            reranked_rankings={"GD-0001": ["DOC-A-C-1"], "GD-0002": ["OTHER-C-1"]},
            predictions={
                "GD-0001": {"classification": "STANDARD_SATISFIED"},
                "GD-0002": {"classification": "INSUFFICIENT_INFORMATION"},
            },
        )
        self.assertEqual(1, report["summary"]["bottleneck_counts"]["CHANNEL_RECALL_MISS"])
        self.assertEqual(0.5, report["summary"]["classification_accuracy"])
        self.assertEqual(0.5, report["stages"]["reranker"]["exact_top5_recall"])

    def test_sanitized_report_removes_case_diagnostics(self) -> None:
        report = {"status": "DIAGNOSED", "case_diagnostics": [{"case_id": "GD-0001"}]}
        self.assertNotIn("case_diagnostics", sanitized_layered_report(report))

    def test_rrf_fusion_rewards_items_present_in_both_channels(self) -> None:
        ranked = fuse_ranked_scores(
            [("vector-only", 0.9), ("both", 0.8)],
            [("text-only", 10.0), ("both", 9.0)],
            vector_weight=0.5,
            mode="rrf",
        )
        self.assertEqual("both", ranked[0])

    def test_expand_ranked_neighbors_preserves_rank_and_deduplicates(self) -> None:
        expanded = expand_ranked_neighbors(
            ["DOC-A-C-2", "DOC-A-C-3", "DOC-B-C-1"],
            document_chunks={
                "DOC-A": ["DOC-A-C-1", "DOC-A-C-2", "DOC-A-C-3", "DOC-A-C-4"],
                "DOC-B": ["DOC-B-C-1"],
            },
            fused_limit=2,
            neighbor_radius=1,
        )
        self.assertEqual(
            ["DOC-A-C-2", "DOC-A-C-1", "DOC-A-C-3", "DOC-A-C-4"],
            expanded,
        )


if __name__ == "__main__":
    unittest.main()
