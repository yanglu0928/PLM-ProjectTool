from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.evidence.domain.locator import (
    EvidenceLocatorError, validate_evidence_locator,
)


class EvidenceLocatorTests(unittest.TestCase):
    def test_all_nine_frozen_variants_have_reproducible_internal_shapes(self) -> None:
        parse_id = str(uuid.uuid4())
        cases = [
            {"locator_type": "DOCUMENT"},
            {"locator_type": "PAGE", "page_no": 12, "bbox": [0.1, 0.2, 0.8, 0.9]},
            {"locator_type": "TEXT_RANGE", "page_no": 12, "start_offset": 0,
             "end_offset": 5, "normalized_fingerprint": "A" * 64},
            {"locator_type": "SECTION", "section_path": "3.2 / Scope"},
            {"locator_type": "PARAGRAPH", "page_no": 12, "paragraph_index": 2},
            {"locator_type": "TABLE_CELL", "table_anchor": "table-3", "row_no": 1,
             "column_no": 4},
            {"locator_type": "SHEET_RANGE", "sheet_name": "调研", "start_cell": "b2",
             "end_cell": "C5"},
            {"locator_type": "SLIDE_SHAPE", "slide_no": 3, "shape_id": "shape-4",
             "bounds": [0, 0, 1, 1]},
            {"locator_type": "STRUCTURED_NODE", "parse_record_id": parse_id,
             "node_id": "node-2", "source_locator": {"locator_type": "PAGE", "page_no": 2}},
        ]
        for locator in cases:
            with self.subTest(kind=locator["locator_type"]):
                result = validate_evidence_locator(locator)
                self.assertEqual(result["locator_type"], locator["locator_type"])
                self.assertIsNot(result, locator)
        self.assertEqual(validate_evidence_locator(cases[2])["normalized_fingerprint"], "a" * 64)
        self.assertEqual(validate_evidence_locator(cases[6])["start_cell"], "B2")

    def test_unknown_or_spoofed_fields_fail_closed(self) -> None:
        cases = [
            {}, {"locator_type": "MODEL_SUMMARY", "text": "guess"},
            {"locator_type": "DOCUMENT", "file_path": "C:/secret"},
            {"locator_type": "PAGE", "page_no": True},
            {"locator_type": "PAGE", "page_no": 1, "bbox": [0, 0, float("nan"), 1]},
            {"locator_type": "PAGE", "page_no": 1, "bbox": [0.5, 0, 0.2, 1]},
            {"locator_type": "TEXT_RANGE", "page_no": 1, "section_path": "3",
             "start_offset": 0, "end_offset": 1, "normalized_fingerprint": "a" * 64},
            {"locator_type": "TEXT_RANGE", "page_no": 1, "start_offset": 2,
             "end_offset": 2, "normalized_fingerprint": "a" * 64},
            {"locator_type": "TEXT_RANGE", "page_no": 1, "start_offset": 0,
             "end_offset": 1, "normalized_fingerprint": "not-a-fingerprint"},
            {"locator_type": "PARAGRAPH", "paragraph_index": 2, "stable_anchor": "x"},
            {"locator_type": "TABLE_CELL", "table_anchor": "t", "row_no": 0, "column_no": 1},
            {"locator_type": "SHEET_RANGE", "sheet_name": "S", "start_cell": "C5",
             "end_cell": "B6"},
            {"locator_type": "SHEET_RANGE", "sheet_name": "S", "start_cell": "XFE1",
             "end_cell": "XFE2"},
            {"locator_type": "SLIDE_SHAPE", "slide_no": 1, "shape_id": " "},
            {"locator_type": "STRUCTURED_NODE", "parse_record_id": str(uuid.uuid4()),
             "node_id": "n", "source_locator": {"locator_type": "STRUCTURED_NODE"}},
            {"locator_type": "STRUCTURED_NODE", "parse_record_id": "bad", "node_id": "n",
             "source_locator": {"locator_type": "PAGE", "page_no": 1}},
        ]
        for locator in cases:
            with self.subTest(locator=locator):
                with self.assertRaises(EvidenceLocatorError):
                    validate_evidence_locator(locator)

    def test_returns_detached_nested_copy(self) -> None:
        locator = {"locator_type": "STRUCTURED_NODE", "parse_record_id": str(uuid.uuid4()),
                   "node_id": "n", "source_locator": {"locator_type": "PAGE", "page_no": 2}}
        result = validate_evidence_locator(locator)
        self.assertIsNot(result["source_locator"], locator["source_locator"])
        locator["source_locator"]["page_no"] = 8
        self.assertEqual(result["source_locator"]["page_no"], 2)


if __name__ == "__main__":
    unittest.main()
