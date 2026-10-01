from __future__ import annotations

import hashlib
import json
import sys
import uuid
from dataclasses import replace
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import (
    ParseResultReadError, VerifiedParseResult,
)
from plm_assistant.modules.evidence.application.parsed_node_proof import (
    EvidenceNodeProofError, ParsedNodeEvidenceProofService,
)


class _Results:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def read(self, *_args, **_kwargs):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class ParsedNodeProofTests(TestCase):
    def setUp(self):
        self.document_id, self.version_id, self.record_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", uuid.uuid4())
        self.profile = "PLAIN_TEXT"
        self.source = {"locator_type": "TEXT_RANGE", "section_path": "plain-text-root",
                       "start_offset": 0, "end_offset": 5,
                       "normalized_fingerprint": "a" * 64}
        self.nodes = [{"node_id": "n-1", "kind": "TEXT_LINE", "text": "Hello",
                       "source_locator": self.source}]
        self.port = _Results(self._result())
        self.proof = ParsedNodeEvidenceProofService(results=self.port)

    def _result(self):
        source_hash = b"x" * 32
        payload = {"schema_version": "1", "document_version_id": str(self.version_id),
                   "source_sha256": source_hash.hex(), "parser_profile": self.profile,
                   "parser_version": "1", "nodes": self.nodes}
        content = json.dumps(payload, separators=(",", ":")).encode()
        return VerifiedParseResult(self.record_id, self.version_id, uuid.uuid4(),
                                   self.profile, "1", source_hash,
                                   hashlib.sha256(content).digest(), content)

    def prove(self, locator):
        return self.proof.prove(self.query, document_id=self.document_id,
                                document_version_id=self.version_id,
                                parse_record_id=self.record_id, locator=locator)

    def test_direct_and_structured_node_match_exact_bytes(self):
        direct = self.prove(self.source)
        self.assertEqual((direct.node_id, direct.locator), ("n-1", self.source))
        self.assertEqual(direct.content_fingerprint, hashlib.sha256(b"Hello").digest())
        self.assertNotIn("Hello", repr(direct))
        structured = {"locator_type": "STRUCTURED_NODE", "parse_record_id": str(self.record_id),
                      "node_id": "n-1", "source_locator": self.source}
        self.assertEqual(self.prove(structured).node_id, "n-1")

    def test_wrong_record_or_node_fails(self):
        for item, code in (
            ({"locator_type": "STRUCTURED_NODE", "parse_record_id": str(uuid.uuid4()),
              "node_id": "n-1", "source_locator": self.source}, "RESOURCE_NOT_FOUND"),
            ({"locator_type": "STRUCTURED_NODE", "parse_record_id": str(self.record_id),
              "node_id": "other", "source_locator": self.source}, "EVIDENCE_RESOLUTION_UNAVAILABLE"),
        ):
            with self.subTest(item=item), self.assertRaises(EvidenceNodeProofError) as caught:
                self.prove(item)
            self.assertEqual(caught.exception.code, code)

    def test_unproduced_section_and_document_rejected_before_port(self):
        for locator in ({"locator_type": "SECTION", "section_path": "A"},
                        {"locator_type": "DOCUMENT"}):
            with self.assertRaisesRegex(EvidenceNodeProofError, "EVIDENCE_RESOLUTION_UNAVAILABLE"):
                self.prove(locator)
        self.assertEqual(self.port.calls, 0)

    def test_wrong_or_ambiguous_position_fails(self):
        wrong = dict(self.source, start_offset=1)
        with self.assertRaisesRegex(EvidenceNodeProofError, "EVIDENCE_RESOLUTION_UNAVAILABLE"):
            self.prove(wrong)
        self.nodes.append({"node_id": "n-2", "kind": "TEXT_LINE", "text": "Other",
                           "source_locator": self.source})
        self.port.value = self._result()
        with self.assertRaisesRegex(EvidenceNodeProofError, "EVIDENCE_RESOLUTION_UNAVAILABLE"):
            self.prove(self.source)

    def test_malformed_or_corrupt_result_fails(self):
        self.port.value = replace(self.port.value, result_sha256=b"z" * 32)
        with self.assertRaises(EvidenceNodeProofError):
            self.prove(self.source)
        self.nodes[0]["kind"] = "DOCX_PARAGRAPH"
        self.port.value = self._result()
        with self.assertRaises(EvidenceNodeProofError):
            self.prove(self.source)
        self.nodes[0]["kind"] = ["TEXT_LINE"]
        self.port.value = self._result()
        with self.assertRaises(EvidenceNodeProofError):
            self.prove(self.source)
        self.nodes[0]["kind"] = "TEXT_LINE"
        self.nodes[0]["text"] = "\ud800"
        self.port.value = self._result()
        with self.assertRaises(EvidenceNodeProofError):
            self.prove(self.source)

    def test_upstream_authorization_failure_not_hidden(self):
        self.port.value = ParseResultReadError("AUTH_ACCESS_DENIED")
        with self.assertRaisesRegex(EvidenceNodeProofError, "AUTH_ACCESS_DENIED"):
            self.prove(self.source)

    def test_supported_parser_positions(self):
        samples = (
            ("PDF_TEXT_THEN_OCR", "PDF_TEXT_LINE", self.source),
            ("IMAGE_OCR", "OCR_LINE", {"locator_type": "PAGE", "page_no": 1, "bbox": [0.1, 0.1, 0.9, 0.9]}),
            ("CSV", "CSV_CELL", {"locator_type": "SHEET_RANGE", "sheet_name": "CSV",
                          "start_cell": "A1", "end_cell": "A1"}),
            ("DOCX", "DOCX_PARAGRAPH", {"locator_type": "PARAGRAPH", "paragraph_index": 1}),
            ("DOCX", "DOCX_TABLE_CELL", {"locator_type": "TABLE_CELL", "table_anchor": "t1",
                                 "row_no": 1, "column_no": 2}),
            ("PPTX", "PPTX_SHAPE", {"locator_type": "SLIDE_SHAPE", "slide_no": 1, "shape_id": "s1"}),
            ("PPTX", "PPTX_TABLE_CELL", {"locator_type": "TABLE_CELL", "table_anchor": "t2",
                                 "row_no": 1, "column_no": 1}),
            ("XLSX", "XLSX_CELL", {"locator_type": "SHEET_RANGE", "sheet_name": "Sheet1",
                           "start_cell": "B2", "end_cell": "B2"}),
        )
        for profile, kind, locator in samples:
            with self.subTest(kind=kind):
                self.profile = profile
                self.nodes[0]["kind"] = kind
                self.nodes[0]["source_locator"] = locator
                self.port.value = self._result()
                self.assertEqual(self.prove(locator).node_id, "n-1")

    def test_csv_empty_cell_does_not_invalidate_nonempty_neighbor(self):
        self.profile = "CSV"
        empty = {"locator_type": "SHEET_RANGE", "sheet_name": "CSV",
                 "start_cell": "A1", "end_cell": "A1"}
        filled = {"locator_type": "SHEET_RANGE", "sheet_name": "CSV",
                  "start_cell": "B1", "end_cell": "B1"}
        self.nodes = [
            {"node_id": "r1c1", "kind": "CSV_CELL", "text": "", "source_locator": empty},
            {"node_id": "r1c2", "kind": "CSV_CELL", "text": "value", "source_locator": filled},
        ]
        self.port.value = self._result()
        self.assertEqual(self.prove(filled).node_id, "r1c2")
        with self.assertRaises(EvidenceNodeProofError):
            self.prove(empty)
