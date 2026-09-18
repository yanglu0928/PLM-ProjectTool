from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.source_type_audit import (  # noqa: E402
    audit_candidate_source_types,
    build_sanitized_source_type_report,
    classify_document_source,
)


class SourceTypeAuditTests(unittest.TestCase):
    def test_explicit_technical_agreement_title_is_eligible(self) -> None:
        result = classify_document_source(
            source_corpus="CONTRACT",
            file_name="PLM 项目技术协议 V1.0.docx",
        )
        self.assertEqual("ELIGIBLE", result["eligibility"])
        self.assertEqual("TECHNICAL_AGREEMENT", result["proposed_source_type"])

    def test_explicit_contract_title_is_eligible(self) -> None:
        result = classify_document_source(
            source_corpus="CONTRACT",
            file_name="技术开发服务合同.pdf",
        )
        self.assertEqual("CONTRACT", result["proposed_source_type"])

    def test_solution_corpus_is_not_falsely_mapped(self) -> None:
        result = classify_document_source(
            source_corpus="SOLUTION",
            file_name="总体设计方案.docx",
        )
        self.assertEqual("INELIGIBLE", result["eligibility"])
        self.assertIsNone(result["proposed_source_type"])

    def test_user_designated_standard_and_survey_corpora_are_eligible(self) -> None:
        for source_type in ("STANDARD_CAPABILITY", "SURVEY"):
            result = classify_document_source(
                source_corpus=source_type,
                file_name="redacted.docx",
            )
            self.assertEqual("ELIGIBLE", result["eligibility"])
            self.assertEqual(source_type, result["proposed_source_type"])
            self.assertEqual("USER_DESIGNATED_SOURCE_LIBRARY", result["reason"])

    def test_audit_marks_existing_mismatch_for_correction(self) -> None:
        candidates = [
            {
                "candidate_id": "GD-C-0001",
                "source_corpus": "CONTRACT",
                "expected_citations": [{"document_id": "CONTRACT-SL-001"}],
            }
        ]
        rows = [{"candidate_id": "GD-C-0001", "source_type": "CONTRACT"}]
        documents = [
            {
                "document_id": "CONTRACT-SL-001",
                "file_name": "PLM 项目技术协议.docx",
            }
        ]
        result = audit_candidate_source_types(candidates, rows, documents)[0]
        self.assertEqual("CORRECTION_REQUIRED", result["audit_status"])
        self.assertEqual("TECHNICAL_AGREEMENT", result["proposed_source_type"])

    def test_report_exposes_coverage_gap_without_customer_content(self) -> None:
        rows = [
            {
                "eligibility": "ELIGIBLE",
                "proposed_source_type": "CONTRACT",
                "audit_status": "VERIFIED",
            },
            {
                "eligibility": "INELIGIBLE",
                "proposed_source_type": None,
                "audit_status": "EXCLUDED_UNSUPPORTED_SOURCE_TYPE",
            },
        ]
        report = build_sanitized_source_type_report(
            rows,
            generated_at="2026-09-17T00:00:00+00:00",
        )
        self.assertEqual("PASS", report["status"])
        self.assertEqual("BLOCKED_MISSING_SOURCE_CORPORA", report["p03_a02_status"])
        self.assertEqual(99, report["summary"]["minimum_case_count_gap"])
        self.assertIn("STANDARD_CAPABILITY", report["summary"]["missing_required_source_types"])
        serialized = str(report)
        self.assertNotIn("总体设计方案", serialized)


if __name__ == "__main__":
    unittest.main()
