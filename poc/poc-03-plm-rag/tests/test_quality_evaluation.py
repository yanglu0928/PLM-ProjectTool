from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.quality_evaluation import (  # noqa: E402
    evaluate_quality,
    lexical_terms,
    normalize_cjk_spacing,
    parse_plain_prediction,
    rank_lexical_overlap,
    searchable_text,
    tsquery_or,
)


class QualityEvaluationTests(unittest.TestCase):
    def test_cjk_ocr_spacing_is_removed_before_term_extraction(self) -> None:
        normalized = normalize_cjk_spacing("合\n同\n的 有 效 组 成 部 分")
        self.assertEqual("合同的有效组成部分", normalized)
        self.assertIn("合同", lexical_terms(f"关于“{normalized}”有哪些约定？"))
        self.assertIn("合同", searchable_text("合\n同\n条\n款").split())

    def test_lexical_overlap_ranks_ocr_spaced_direct_evidence_first(self) -> None:
        ranked = rank_lexical_overlap(
            "关于合同有效组成部分有哪些约定？",
            {
                "C-OTHER": "系统支持项目计划与资源分配。",
                "C-TARGET": "该附件是合\n同\n的\n有\n效\n组\n成\n部\n分。",
            },
        )
        self.assertEqual("C-TARGET", ranked[0])

    def test_lexical_terms_prefers_quoted_subject(self) -> None:
        terms = lexical_terms('参考资料中，关于“工程变更、ECO”采用了什么方式？')
        self.assertIn("eco", terms)
        self.assertIn("工程", terms)
        self.assertNotIn("参考", terms)

    def test_searchable_text_and_tsquery_are_safe(self) -> None:
        body = searchable_text("工程变更 ECO-01")
        self.assertIn("工程", body)
        query = tsquery_or(["工程", "eco-01", "bad'value"])
        self.assertNotIn("'", query)
        self.assertIn(" | ", query)

    def test_quality_report_passes_complete_results(self) -> None:
        cases = []
        retrievals = {}
        predictions = {}
        for index in range(100):
            case_id = f"GD-{index:04d}"
            chunk_id = f"C-{index:04d}"
            cases.append(
                {
                    "case_id": case_id,
                    "expected_relevant_chunk_ids": [chunk_id],
                    "expected_classification": "STANDARD_SATISFIED",
                }
            )
            retrievals[case_id] = [chunk_id]
            predictions[case_id] = {
                "classification": "STANDARD_SATISFIED",
                "citation_chunk_ids": [chunk_id],
            }
        report = evaluate_quality(
            cases,
            retrievals,
            predictions,
            reranker_live_count=100,
            gin_index_used=True,
            hnsw_index_used=True,
        )
        self.assertEqual("PASS", report["status"])
        self.assertEqual(1.0, report["summary"]["top5_recall"])
        self.assertEqual(1.0, report["summary"]["classification_accuracy"])
        self.assertEqual(1.0, report["summary"]["citation_accuracy"])
        self.assertEqual(
            100,
            report["diagnostics"]["by_source_type"]["UNKNOWN"][
                "same_document_retrieval_hits"
            ],
        )

    def test_invalid_or_wrong_citation_fails(self) -> None:
        case = {
            "case_id": "GD-0001",
            "expected_relevant_chunk_ids": ["EXPECTED"],
            "expected_classification": "NON_STANDARD",
        }
        report = evaluate_quality(
            [case],
            {"GD-0001": ["EXPECTED", "OTHER"]},
            {
                "GD-0001": {
                    "classification": "STANDARD_SATISFIED",
                    "citation_chunk_ids": ["OUTSIDE"],
                }
            },
            reranker_live_count=1,
            gin_index_used=True,
            hnsw_index_used=True,
        )
        self.assertEqual("FAIL", report["status"])
        self.assertEqual(0.0, report["summary"]["citation_accuracy"])
        self.assertEqual(1, report["summary"]["invalid_citation_case_count"])

    def test_plain_prediction_parser_accepts_constrained_result(self) -> None:
        prediction = parse_plain_prediction(
            " PARTIALLY_SATISFIED | CHUNK-002 ",
            valid_chunk_ids=["CHUNK-001", "CHUNK-002"],
        )
        self.assertEqual("PARTIALLY_SATISFIED", prediction["classification"])
        self.assertEqual(["CHUNK-002"], prediction["citation_chunk_ids"])

    def test_plain_prediction_parser_rejects_invented_chunk(self) -> None:
        with self.assertRaises(ValueError):
            parse_plain_prediction(
                "STANDARD_SATISFIED|INVENTED",
                valid_chunk_ids=["CHUNK-001"],
            )

    def test_plain_prediction_parser_rejects_extra_prose(self) -> None:
        with self.assertRaises(ValueError):
            parse_plain_prediction(
                "Result: STANDARD_SATISFIED|CHUNK-001",
                valid_chunk_ids=["CHUNK-001"],
            )

    def test_plain_prediction_parser_accepts_one_framed_final_line(self) -> None:
        prediction = parse_plain_prediction(
            "Internal analysis may appear here.\nFINAL:NON_STANDARD|CHUNK-001",
            valid_chunk_ids=["CHUNK-001"],
        )
        self.assertEqual("NON_STANDARD", prediction["classification"])

    def test_plain_prediction_parser_rejects_ambiguous_final_lines(self) -> None:
        with self.assertRaises(ValueError):
            parse_plain_prediction(
                "FINAL:NON_STANDARD|CHUNK-001\nFINAL:STANDARD_SATISFIED|CHUNK-001",
                valid_chunk_ids=["CHUNK-001"],
            )


if __name__ == "__main__":
    unittest.main()
