from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.review_suggestions import (  # noqa: E402
    build_review_suggestions,
    build_sanitized_suggestion_report,
)


def candidate(candidate_id: str, *, corpus: str, content: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "source_corpus": corpus,
        "candidate_content": content,
        "expected_citations": [
            {
                "document_id": "DOC-001",
                "chunk_id": "CHUNK-001",
                "source_locators": ["word/paragraph/1"],
            }
        ],
    }


class ReviewSuggestionTests(unittest.TestCase):
    def test_contract_source_and_explicit_capability_are_prefilled(self) -> None:
        suggestions = build_review_suggestions(
            [
                candidate(
                    "GD-C-0001",
                    corpus="CONTRACT",
                    content="产品结构管理。系统支持 EBOM 版本管理和审批流程。",
                )
            ]
        )
        row = suggestions[0]
        self.assertEqual("CONTRACT", row["source_type"])
        self.assertEqual("STANDARD_SATISFIED", row["classification"])
        self.assertEqual("PENDING", row["review_status"])
        self.assertEqual("", row["reviewed_by"])
        self.assertEqual(["word/paragraph/1"], row["citation_locators"])
        self.assertIn("EBOM", row["answer_terms"])

    def test_solution_source_type_is_not_fabricated(self) -> None:
        suggestions = build_review_suggestions(
            [
                candidate(
                    "GD-C-0002",
                    corpus="SOLUTION",
                    content="数据迁移方案。历史图文档需要人工确认后导入。",
                )
            ]
        )
        row = suggestions[0]
        self.assertEqual("", row["source_type"])
        self.assertEqual("HUMAN_CONFIRMATION_REQUIRED", row["classification"])
        self.assertIn("不在锁定来源类型枚举", row["notes"])

    def test_duplicate_topics_produce_distinct_queries(self) -> None:
        records = [
            candidate(
                f"GD-C-{index:04d}",
                corpus="CONTRACT",
                content="权限管理。系统支持项目权限和文档权限。",
            )
            for index in range(1, 4)
        ]
        suggestions = build_review_suggestions(records)
        self.assertEqual(3, len({row["query"] for row in suggestions}))

    def test_sanitized_report_excludes_suggestion_text(self) -> None:
        sensitive = "CONFIDENTIAL-QUERY-TEXT"
        suggestions = [
            {
                "candidate_id": "GD-C-0001",
                "query": sensitive,
                "source_type": "CONTRACT",
                "classification": "HUMAN_CONFIRMATION_REQUIRED",
                "answer_terms": ["secret"],
                "citation_locators": ["source/1"],
                "review_status": "PENDING",
                "reviewed_by": "",
                "reviewed_at": "",
                "notes": "local",
            }
        ]
        report = build_sanitized_suggestion_report(
            suggestions,
            generated_at="2026-09-17T00:00:00+00:00",
        )
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(sensitive, serialized)
        self.assertNotIn("secret", serialized)
        self.assertFalse(report["privacy"]["external_ai_service_called"])


if __name__ == "__main__":
    unittest.main()
