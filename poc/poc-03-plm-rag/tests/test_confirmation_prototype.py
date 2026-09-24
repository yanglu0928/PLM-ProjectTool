from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.confirmation_prototype import (  # noqa: E402
    build_confirmation_tasks,
    build_evidence_navigator_html,
    build_sanitized_confirmation_report,
)


class ConfirmationPrototypeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = {
            "candidate_id": "GD-C-0001",
            "source_corpus": "SOLUTION",
            "expected_citations": [
                {
                    "document_id": "SOLUTION-SL-001",
                    "source_locators": ["word/paragraph/10"],
                }
            ],
        }

    def test_missing_source_type_explains_exact_required_input(self) -> None:
        rows = [
            {
                "candidate_id": "GD-C-0001",
                "query": "需要确认什么？",
                "source_type": "",
                "classification": "HUMAN_CONFIRMATION_REQUIRED",
                "review_status": "APPROVED",
                "reviewed_by": "Reviewer",
                "reviewed_at": "2026-09-17",
            }
        ]
        task = build_confirmation_tasks([self.candidate], rows)[0]
        self.assertEqual("待补充", task["current_status"])
        self.assertEqual("需要补充资料", task["human_decision"])
        self.assertIn("标准能力、合同、技术协议或调研", task["confirmation_prompt"])
        self.assertIn("不能自动代填", task["ai_advice"])

    def test_complete_approved_row_is_preserved_as_confirmed(self) -> None:
        candidate = dict(self.candidate, source_corpus="CONTRACT")
        rows = [
            {
                "candidate_id": "GD-C-0001",
                "query": "合同约定是什么？",
                "source_type": "CONTRACT",
                "classification": "STANDARD_SATISFIED",
                "answer_terms": "合同约定",
                "confirmed_locator": "word/paragraph/10",
                "review_status": "APPROVED",
                "reviewed_by": "Reviewer",
                "reviewed_at": "2026-09-17",
            }
        ]
        task = build_confirmation_tasks([candidate], rows)[0]
        self.assertEqual("已确认", task["current_status"])
        self.assertEqual("同意AI建议", task["human_decision"])
        self.assertEqual("低", task["risk_level"])

    def test_approved_status_cannot_bypass_other_required_fields(self) -> None:
        candidate = dict(self.candidate, source_corpus="CONTRACT")
        rows = [
            {
                "candidate_id": "GD-C-0001",
                "query": "合同约定是什么？",
                "source_type": "CONTRACT",
                "classification": "STANDARD_SATISFIED",
                "answer_terms": "",
                "confirmed_locator": "word/paragraph/10",
                "review_status": "APPROVED",
                "reviewed_by": "Reviewer",
                "reviewed_at": "2026-09-17",
            }
        ]
        task = build_confirmation_tasks([candidate], rows)[0]
        self.assertEqual("待补充", task["current_status"])
        self.assertEqual("需要补充资料", task["human_decision"])

    def test_sanitized_report_does_not_leak_query_or_reviewer(self) -> None:
        task = {
            "risk_level": "中",
            "current_status": "待补充",
            "original_review_status": "APPROVED",
            "evidence_link": "evidence.html#1",
            "source_type": "",
            "ai_finding": "CONFIDENTIAL-QUERY",
            "reviewed_by": "CONFIDENTIAL-REVIEWER",
        }
        report = build_sanitized_confirmation_report(
            [task], generated_at="2026-09-17T00:00:00+00:00"
        )
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("CONFIDENTIAL-QUERY", serialized)
        self.assertNotIn("CONFIDENTIAL-REVIEWER", serialized)

    def test_navigator_escapes_content_and_has_candidate_anchor(self) -> None:
        page = build_evidence_navigator_html(
            [
                {
                    "candidate_id": "GD-C-0001",
                    "query": "<script>alert(1)</script>",
                    "source_name": "sample.docx",
                    "document_id": "DOC-1",
                    "content": "客户内容 <b>不得执行</b>",
                    "locators": ["word/paragraph/10"],
                    "original_url": "file:///D:/sample.docx",
                }
            ]
        )
        self.assertIn('id="GD-C-0001"', page)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertIn("打开原文件", page)


if __name__ == "__main__":
    unittest.main()
