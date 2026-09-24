from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.prompt_v3 import (  # noqa: E402
    OUTPUT_CLASSIFICATIONS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_case_payload,
    payload_contains_forbidden_keys,
    prediction_schema,
)


class PromptV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {
            "case_id": "DEV-0001",
            "project_id": "P-1",
            "question_type": "CAPABILITY_FIT",
            "query": "合同要求的专用处理是否由标准能力完整满足？",
            "expected_classification": "NON_STANDARD",
            "expected_relevant_chunk_ids": ["REQ-C-1"],
            "expected_answer_terms": ["private-label"],
        }
        self.chunks = {
            "REQ-C-1": {
                "scope": "PROJECT",
                "project_id": "P-1",
                "chunk_id": "REQ-C-1",
                "document_id": "CONTRACT-1",
                "source_corpus": "CONTRACT",
                "source_locators": ["page/1"],
                "text": "合\n同\n要\n求\n专\n用\n处\n理。",
            },
            "CAP-C-1": {
                "scope": "PROJECT",
                "project_id": "P-1",
                "chunk_id": "CAP-C-1",
                "document_id": "STANDARD-1",
                "source_corpus": "STANDARD_CAPABILITY",
                "source_locators": ["section/2"],
                "text": "标准能力仅支持通用处理。",
            },
        }

    def test_prompt_version_and_task_split_are_explicit(self) -> None:
        self.assertEqual("v3", PROMPT_VERSION)
        self.assertIn("DOCUMENT_ASSERTION", SYSTEM_PROMPT)
        self.assertIn("CAPABILITY_FIT", SYSTEM_PROMPT)
        self.assertIn("不能默认引用第 1 名", SYSTEM_PROMPT)
        self.assertIn("NOT_APPLICABLE", OUTPUT_CLASSIFICATIONS)

    def test_capability_fit_payload_contains_dual_source_evidence_without_gold(self) -> None:
        payload = build_case_payload(
            self.case,
            ["REQ-C-1"],
            ["CAP-C-1"],
            self.chunks,
        )
        self.assertEqual("合同要求专用处理。", payload["requirement_contexts"][0]["text"])
        self.assertEqual(
            "STANDARD_CAPABILITY",
            payload["capability_contexts"][0]["source_type"],
        )
        self.assertFalse(payload_contains_forbidden_keys(payload))
        self.assertNotIn("private-label", str(payload))

    def test_question_type_must_be_explicit(self) -> None:
        self.case.pop("question_type")
        with self.assertRaisesRegex(ValueError, "question_type"):
            build_case_payload(
                self.case, ["REQ-C-1"], ["CAP-C-1"], self.chunks
            )

    def test_capability_fit_requires_capability_context(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires standard capability"):
            build_case_payload(self.case, ["REQ-C-1"], [], self.chunks)

    def test_document_assertion_rejects_capability_context(self) -> None:
        self.case["question_type"] = "DOCUMENT_ASSERTION"
        with self.assertRaisesRegex(ValueError, "must not receive"):
            build_case_payload(
                self.case, ["REQ-C-1"], ["CAP-C-1"], self.chunks
            )

    def test_cross_project_context_fails_closed(self) -> None:
        self.chunks["CAP-C-1"]["project_id"] = "P-2"
        with self.assertRaisesRegex(ValueError, "another ProjectId"):
            build_case_payload(
                self.case, ["REQ-C-1"], ["CAP-C-1"], self.chunks
            )

    def test_schema_requires_auditable_decision_fields(self) -> None:
        item_schema = prediction_schema()["properties"]["items"]["items"]
        required = set(item_schema["required"])
        self.assertTrue(
            {
                "evidence_match",
                "evidence_sufficiency",
                "requirement_coverage",
                "customization_basis",
                "decision_basis",
                "citation_chunk_ids",
            }.issubset(required)
        )
        self.assertEqual(
            "NOT_APPLICABLE",
            item_schema["allOf"][0]["then"]["properties"]["classification"][
                "const"
            ],
        )
        self.assertEqual(
            list(OUTPUT_CLASSIFICATIONS[:-1]),
            item_schema["allOf"][1]["then"]["properties"]["classification"][
                "enum"
            ],
        )


if __name__ == "__main__":
    unittest.main()
