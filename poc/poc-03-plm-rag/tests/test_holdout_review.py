from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.holdout_review import (  # noqa: E402
    sanitized_suggestion_report,
    validate_suggestion,
)


def candidate() -> dict:
    return {
        "candidate_id": "HO-C-0001",
        "candidate_content": "系统支持物料编码自动生成，并允许管理员配置编码规则。",
    }


def suggestion() -> dict:
    return {
        "candidate_id": "HO-C-0001",
        "question": "系统是否支持按可配置规则自动生成物料编码？",
        "classification": "STANDARD_SATISFIED",
        "classification_reason": "证据直接说明系统支持自动生成，并允许配置编码规则。",
        "answer_terms": ["物料编码", "自动生成", "配置编码规则"],
        "evidence_quote": "系统支持物料编码自动生成，并允许管理员配置编码规则。",
    }


class HoldoutReviewTests(unittest.TestCase):
    def test_valid_suggestion_is_normalized(self) -> None:
        result = validate_suggestion(candidate(), suggestion())
        self.assertEqual(result["classification_display"], "标准满足（STANDARD_SATISFIED）")
        self.assertEqual(len(result["answer_terms"]), 3)

    def test_ungrounded_quote_is_replaced_with_exact_source_text(self) -> None:
        invalid = suggestion()
        invalid["evidence_quote"] = "证据中没有出现的内容"
        result = validate_suggestion(candidate(), invalid)
        self.assertTrue(result["evidence_quote_repaired"])
        self.assertIn(result["evidence_quote"], candidate()["candidate_content"])

    def test_empty_reason_uses_local_class_definition(self) -> None:
        valid = suggestion()
        valid["classification_reason"] = ""
        result = validate_suggestion(candidate(), valid)
        self.assertIn("标准能力", result["classification_reason"])

    def test_ungrounded_answer_terms_are_replaced_from_source(self) -> None:
        invalid = suggestion()
        invalid["answer_terms"] = ["不存在术语一", "不存在术语二"]
        result = validate_suggestion(candidate(), invalid)
        self.assertTrue(result["answer_terms_repaired"])
        self.assertTrue(all(term in candidate()["candidate_content"] for term in result["answer_terms"]))

    def test_duplicate_questions_fail_report(self) -> None:
        first = validate_suggestion(candidate(), suggestion())
        second = {**first, "candidate_id": "HO-C-0002"}
        report = sanitized_suggestion_report(
            [first, second],
            expected_count=2,
            api_call_count=2,
            cached_count=0,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["checks"]["questions_unique"])


if __name__ == "__main__":
    unittest.main()
