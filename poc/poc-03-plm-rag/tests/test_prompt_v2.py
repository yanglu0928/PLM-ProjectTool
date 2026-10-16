from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.prompt_v2 import (  # noqa: E402
    FINAL_CLASSIFICATIONS,
    SYSTEM_PROMPT,
    build_case_payload,
    payload_contains_forbidden_keys,
    prediction_schema,
)


class PromptV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {
            "case_id": "GD-0001",
            "source_type": "CONTRACT",
            "query": "合同中有哪些明确约定？",
            "expected_classification": "NON_STANDARD",
            "expected_relevant_chunk_ids": ["CONTRACT-SL-001-C-1"],
            "expected_answer_terms": ["private-label"],
        }
        self.chunks = {
            "CONTRACT-SL-001-C-1": {
                "chunk_id": "CONTRACT-SL-001-C-1",
                "document_id": "CONTRACT-SL-001",
                "source_corpus": "CONTRACT",
                "source_locators": ["page/1", "page/2"],
                "text": "合\n同\n明\n确\n约\n定。",
            }
        }

    def test_only_five_final_labels_are_allowed(self) -> None:
        self.assertEqual(5, len(FINAL_CLASSIFICATIONS))
        self.assertNotIn("HUMAN_CONFIRMATION_REQUIRED", FINAL_CLASSIFICATIONS)
        enum = prediction_schema()["properties"]["items"]["items"]["properties"][
            "classification"
        ]["enum"]
        self.assertEqual(list(FINAL_CLASSIFICATIONS), enum)

    def test_prompt_requires_ordered_evidence_gates(self) -> None:
        self.assertLess(SYSTEM_PROMPT.index("匹配性"), SYSTEM_PROMPT.index("充分性"))
        self.assertLess(SYSTEM_PROMPT.index("充分性"), SYSTEM_PROMPT.index("满足程度"))
        self.assertIn("不能仅因资料未提及", SYSTEM_PROMPT)

    def test_payload_normalizes_ocr_and_excludes_golden_fields(self) -> None:
        payload = build_case_payload(
            self.case, ["CONTRACT-SL-001-C-1"], self.chunks
        )
        self.assertEqual("合同明确约定。", payload["contexts"][0]["text"])
        self.assertFalse(payload_contains_forbidden_keys(payload))
        self.assertNotIn("expected_classification", payload)
        self.assertNotIn("private-label", str(payload))

    def test_cross_source_context_is_rejected(self) -> None:
        self.chunks["CONTRACT-SL-001-C-1"]["source_corpus"] = "SURVEY"
        with self.assertRaisesRegex(ValueError, "source type"):
            build_case_payload(
                self.case, ["CONTRACT-SL-001-C-1"], self.chunks
            )

    def test_unknown_context_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown context"):
            build_case_payload(self.case, ["UNKNOWN"], self.chunks)


if __name__ == "__main__":
    unittest.main()
