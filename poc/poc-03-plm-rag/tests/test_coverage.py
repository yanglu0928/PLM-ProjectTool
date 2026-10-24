from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.coverage import (  # noqa: E402
    REQUIRED_CLASSIFICATIONS,
    REQUIRED_SOURCE_TYPES,
    WORKFLOW_ONLY_CLASSIFICATIONS,
    audit_golden_dataset_coverage,
)


def case(index: int, source_type: str, classification: str) -> dict:
    return {
        "query": f"unique query {index}",
        "project_id": "PROJECT-A",
        "source_type": source_type,
        "expected_classification": classification,
        "expected_relevant_chunk_ids": [f"CHUNK-{index}"],
        "expected_citations": [{"document_id": f"DOC-{index % 8}"}],
    }


class GoldenDatasetCoverageTests(unittest.TestCase):
    def test_balanced_dataset_passes_without_exposing_queries(self) -> None:
        source_types = sorted(REQUIRED_SOURCE_TYPES)
        classifications = sorted(REQUIRED_CLASSIFICATIONS)
        cases = [
            case(
                index,
                source_types[index % len(source_types)],
                classifications[index % len(classifications)],
            )
            for index in range(100)
        ]
        report = audit_golden_dataset_coverage({"cases": cases})
        self.assertEqual("PASS", report["status"])
        self.assertNotIn("queries", report)
        self.assertEqual(100, report["summary"]["unique_query_count"])

    def test_duplicate_and_single_label_dataset_fails(self) -> None:
        cases = [
            {
                **case(index, "SURVEY", "STANDARD_SATISFIED"),
                "query": "same query",
            }
            for index in range(109)
        ]
        report = audit_golden_dataset_coverage({"cases": cases})
        self.assertEqual("FAIL", report["status"])
        self.assertEqual(1, report["summary"]["unique_query_count"])
        self.assertEqual(108, report["summary"]["duplicate_query_count"])
        self.assertIn("CONTRACT", report["missing_source_types"])
        self.assertIn("NON_STANDARD", report["missing_classifications"])

    def test_workflow_only_classification_is_rejected_from_final_dataset(self) -> None:
        source_types = sorted(REQUIRED_SOURCE_TYPES)
        classifications = sorted(REQUIRED_CLASSIFICATIONS)
        cases = [
            case(
                index,
                source_types[index % len(source_types)],
                classifications[index % len(classifications)],
            )
            for index in range(100)
        ]
        cases[0]["expected_classification"] = next(iter(WORKFLOW_ONLY_CLASSIFICATIONS))

        report = audit_golden_dataset_coverage({"cases": cases})

        self.assertEqual("FAIL", report["status"])
        self.assertFalse(report["checks"]["no_workflow_only_classifications"])
        self.assertEqual(1, report["summary"]["workflow_only_classification_count"])


if __name__ == "__main__":
    unittest.main()
