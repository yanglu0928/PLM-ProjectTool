from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.holdout_failure_analysis import (  # noqa: E402
    analyze_holdout_failures,
    sanitized_failure_analysis,
)


class HoldoutFailureAnalysisTests(unittest.TestCase):
    def test_reports_rank_one_citation_bias_and_term_coverage(self) -> None:
        cases = [
            {
                "case_id": "HO-0001",
                "source_type": "CONTRACT",
                "expected_classification": "NON_STANDARD",
                "expected_relevant_chunk_ids": ["DOC-C-expected"],
                "expected_answer_terms": ["alpha", "beta"],
            }
        ]
        report = analyze_holdout_failures(
            cases,
            {"HO-0001": ["DOC-C-cited", "DOC-C-expected"]},
            {
                "HO-0001": {
                    "classification": "STANDARD_SATISFIED",
                    "citation_chunk_ids": ["DOC-C-cited"],
                }
            },
            chunks_by_id={"DOC-C-cited": {"text": "alpha beta"}},
        )
        self.assertEqual(1, report["summary"]["classification_miss_count"])
        self.assertEqual(1, report["summary"]["citation_miss_count"])
        self.assertEqual(1, report["summary"]["rank1_citation_count"])
        self.assertEqual(
            1,
            report["summary"]["citation_miss_full_expected_term_coverage_count"],
        )
        self.assertEqual(
            {"cases": 1, "citation_hits": 0},
            report["citation_by_expected_chunk_rank"]["2"],
        )

    def test_requirement_source_summary_is_aggregate_only(self) -> None:
        cases = [
            {
                "case_id": "HO-0001",
                "source_type": "TECHNICAL_AGREEMENT",
                "expected_classification": "INSUFFICIENT_INFORMATION",
                "expected_relevant_chunk_ids": ["DOC-C-1"],
                "expected_answer_terms": [],
            },
            {
                "case_id": "HO-0002",
                "source_type": "STANDARD_CAPABILITY",
                "expected_classification": "STANDARD_SATISFIED",
                "expected_relevant_chunk_ids": ["STD-C-1"],
                "expected_answer_terms": [],
            },
        ]
        report = analyze_holdout_failures(
            cases,
            {"HO-0001": ["DOC-C-1"], "HO-0002": ["STD-C-1"]},
            {
                "HO-0001": {
                    "classification": "STANDARD_SATISFIED",
                    "citation_chunk_ids": ["DOC-C-1"],
                },
                "HO-0002": {
                    "classification": "STANDARD_SATISFIED",
                    "citation_chunk_ids": ["STD-C-1"],
                },
            },
        )
        self.assertEqual(1, report["summary"]["requirement_source_case_count"])
        self.assertEqual(
            0, report["summary"]["requirement_source_classification_hit_count"]
        )

    def test_sanitized_report_removes_case_diagnostics(self) -> None:
        report = {
            "status": "DIAGNOSED",
            "case_diagnostics": [{"case_id": "HO-0001"}],
            "privacy": {"queries_in_report": False},
        }
        sanitized = sanitized_failure_analysis(report)
        self.assertNotIn("case_diagnostics", sanitized)
        self.assertEqual("DIAGNOSED", sanitized["status"])


if __name__ == "__main__":
    unittest.main()
