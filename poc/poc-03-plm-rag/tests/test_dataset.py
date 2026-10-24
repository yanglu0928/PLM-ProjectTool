from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.dataset import (  # noqa: E402
    build_candidate_records,
    build_sanitized_report,
    chunk_document,
)


class DatasetTests(unittest.TestCase):
    def test_chunks_preserve_project_scope_and_source_location(self) -> None:
        parsed = {
            "blocks": [
                {
                    "text": "需求管理需要保留版本、状态和来源追溯。" * 8,
                    "source_locator": "word/paragraph/1",
                    "page": 1,
                    "section": "需求管理",
                    "type": "paragraph",
                },
                {
                    "text": "所有正式需求必须经过人工确认。" * 8,
                    "source_locator": "word/paragraph/2",
                    "page": 1,
                    "section": "需求管理",
                    "type": "paragraph",
                },
            ]
        }
        chunks = chunk_document(
            "SL-001", parsed, "PROJECT-A", source_corpus="SOLUTION", max_chars=150
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk["scope"] == "PROJECT" for chunk in chunks))
        self.assertTrue(all(chunk["project_id"] == "PROJECT-A" for chunk in chunks))
        self.assertTrue(all(chunk["source_corpus"] == "SOLUTION" for chunk in chunks))
        self.assertTrue(all(chunk["source_locators"] for chunk in chunks))

    def test_candidate_selection_is_balanced_and_pending_review(self) -> None:
        chunks = []
        for document_id in ("SL-001", "SL-002"):
            for index in range(60):
                text = f"{document_id}-{index}-" + ("测试内容" * 30)
                chunks.append(
                    {
                        "chunk_id": f"{document_id}-C-{index:03d}",
                        "document_id": document_id,
                        "scope": "PROJECT",
                        "project_id": "PROJECT-A",
                        "source_corpus": "SOLUTION",
                        "text": text,
                        "text_sha256": "0" * 64,
                        "character_count": len(text),
                        "source_locators": [f"source/{index}"],
                    }
                )
        candidates = build_candidate_records(chunks, target_count=100)
        self.assertEqual(100, len(candidates))
        self.assertEqual({"PENDING_HUMAN_REVIEW"}, {item["status"] for item in candidates})
        counts = {
            document_id: sum(
                item["expected_citations"][0]["document_id"] == document_id
                for item in candidates
            )
            for document_id in ("SL-001", "SL-002")
        }
        self.assertEqual({"SL-001": 50, "SL-002": 50}, counts)

    def test_sanitized_report_does_not_contain_candidate_content(self) -> None:
        sensitive_text = "CONFIDENTIAL-CUSTOMER-CONTENT"
        document = {"blocks": [{"text": sensitive_text}]}
        chunk = {
            "chunk_id": "SL-001-C-1",
            "document_id": "SL-001",
            "scope": "PROJECT",
            "project_id": "PROJECT-A",
            "source_corpus": "CONTRACT",
            "text": sensitive_text,
            "text_sha256": "0" * 64,
            "character_count": len(sensitive_text),
            "source_locators": ["source/1"],
        }
        candidate = {
            "expected_citations": [{"document_id": "SL-001"}],
        }
        report = build_sanitized_report(
            documents=[document],
            chunks=[chunk],
            candidates=[candidate],
            target_count=100,
            local_output_location="ignored",
            generated_at="2026-09-17T00:00:00+00:00",
        )
        self.assertNotIn(sensitive_text, json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
