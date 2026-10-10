from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError,
    DocumentReadQuery,
    DocumentVersionView,
)
from plm_assistant.modules.document.application.read_parse_result import (
    ParseResultReadError,
    VerifiedParseResult,
)
from plm_assistant.modules.document.application.resolve_parse_nodes import (
    DocumentNodeLocationError,
    DocumentNodeLocationService,
    DocumentVersionLocationService,
)


class _Results:
    def __init__(self, value: object) -> None:
        self.value = value
        self.calls = 0

    def read(self, *_args, **_kwargs):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class _Versions:
    def __init__(self, value: object) -> None:
        self.value = value

    def get_version(self, *_args):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class DocumentNodeLocationTests(TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.record_id = uuid.uuid4()
        self.source_hash = hashlib.sha256(b"source").digest()
        self.query = DocumentReadQuery(
            b"s" * 32, uuid.uuid4(), "PROJECT", self.project_id,
        )
        self.profile = "PLAIN_TEXT"
        self.parser_version = "1"
        self.nodes = [self._node(
            "line-1", "TEXT_LINE", "Alpha",
            {"locator_type": "TEXT_RANGE", "section_path": "plain-text-root",
             "start_offset": 0, "end_offset": 5,
             "normalized_fingerprint": hashlib.sha256(b"Alpha").hexdigest()},
        )]
        self.results = _Results(self._result())
        self.service = DocumentNodeLocationService(results=self.results)
        self.versions = _Versions(DocumentVersionView(
            self.version_id, self.document_id, 1, self.source_hash.hex(), 6,
            "text/plain", "AVAILABLE", None, datetime.now(timezone.utc), None,
        ))
        self.document_locations = DocumentVersionLocationService(
            versions=self.versions,
        )

    @staticmethod
    def _node(node_id: str, kind: str, text: str,
              locator: dict[str, object]) -> dict[str, object]:
        value: dict[str, object] = {
            "node_id": node_id,
            "kind": kind,
            "text": text,
            "source_locator": locator,
        }
        if kind == "OCR_LINE":
            value["confidence"] = 0.91
        return value

    def _result(self) -> VerifiedParseResult:
        payload: dict[str, object] = {
            "schema_version": "1",
            "document_version_id": str(self.version_id),
            "source_sha256": self.source_hash.hex(),
            "parser_profile": self.profile,
            "parser_version": self.parser_version,
            "nodes": self.nodes,
        }
        if any(node["kind"] == "OCR_LINE" for node in self.nodes):
            payload["ocr_model_fingerprint"] = "a" * 64
        content = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()
        return VerifiedParseResult(
            self.record_id, self.version_id, uuid.uuid4(), self.profile,
            self.parser_version, self.source_hash,
            hashlib.sha256(content).digest(), content,
        )

    def _resolve(self, node_ids: tuple[str, ...] = ("line-1",)):
        return self.service.resolve(
            self.query, document_id=self.document_id,
            document_version_id=self.version_id,
            parse_record_id=self.record_id, node_ids=node_ids,
        )

    def test_resolves_exact_nodes_and_fixed_authorized_content_path(self):
        self.nodes.append(self._node(
            "line-2", "TEXT_LINE", "Beta",
            {"locator_type": "TEXT_RANGE", "section_path": "plain-text-root",
             "start_offset": 6, "end_offset": 10,
             "normalized_fingerprint": hashlib.sha256(b"Beta").hexdigest()},
        ))
        self.results.value = self._result()
        result = self._resolve(("line-1", "line-2"))
        self.assertEqual(tuple(item.node_id for item in result.locations),
                         ("line-1", "line-2"))
        self.assertEqual(result.locations[0].locator, {
            "locator_type": "STRUCTURED_NODE",
            "parse_record_id": str(self.record_id),
            "node_id": "line-1",
            "source_locator": self.nodes[0]["source_locator"],
        })
        self.assertEqual(
            result.content_url,
            f"/api/v1/projects/{self.project_id}/documents/{self.document_id}"
            f"/versions/{self.version_id}/content",
        )
        self.assertEqual(result.locations[0].precision, "PARSED_NODE")
        self.assertNotIn("line-1", repr(result.locations[0]))
        self.assertNotIn("Alpha", repr(result.locations[0]))

    def test_supports_every_published_parser_position(self):
        samples = (
            ("PDF_TEXT_THEN_OCR", "1", "PDF_TEXT_LINE",
             {"locator_type": "TEXT_RANGE", "page_no": 2, "start_offset": 0,
              "end_offset": 5, "normalized_fingerprint": "a" * 64}),
            ("IMAGE_OCR", "1", "OCR_LINE",
             {"locator_type": "PAGE", "page_no": 1,
              "bbox": [0.1, 0.1, 0.9, 0.9]}),
            ("CSV", "1", "CSV_CELL",
             {"locator_type": "SHEET_RANGE", "sheet_name": "CSV",
              "start_cell": "A1", "end_cell": "A1"}),
            ("DOCX", "1", "DOCX_PARAGRAPH",
             {"locator_type": "PARAGRAPH", "paragraph_index": 1}),
            ("DOCX", "2", "DOCX_SECTION",
             {"locator_type": "SECTION", "section_path": "word/heading/2/1"}),
            ("DOCX", "1", "DOCX_TABLE_CELL",
             {"locator_type": "TABLE_CELL", "table_anchor": "table-1",
              "row_no": 1, "column_no": 2}),
            ("PPTX", "1", "PPTX_SHAPE",
             {"locator_type": "SLIDE_SHAPE", "slide_no": 2,
              "shape_id": "shape-1"}),
            ("PPTX", "1", "PPTX_TABLE_CELL",
             {"locator_type": "TABLE_CELL", "table_anchor": "slide-2-table-1",
              "row_no": 1, "column_no": 1}),
            ("XLSX", "1", "XLSX_CELL",
             {"locator_type": "SHEET_RANGE", "sheet_name": "Sheet1",
              "start_cell": "B2", "end_cell": "B2"}),
        )
        for profile, version, kind, locator in samples:
            with self.subTest(kind=kind):
                self.profile, self.parser_version = profile, version
                node_id = "heading:1" if kind == "DOCX_SECTION" else "node-1"
                self.nodes = [self._node(node_id, kind, "value", locator)]
                self.results.value = self._result()
                result = self._resolve((node_id,))
                self.assertEqual(
                    result.locations[0].locator["source_locator"], locator,
                )
                self.assertTrue(result.locations[0].display_label)

    def test_unknown_empty_duplicate_or_unsorted_nodes_fail_closed(self):
        for node_ids in (
            ("missing",), (), ("line-1", "line-1"), ("line-2", "line-1"),
        ):
            with self.subTest(node_ids=node_ids), \
                    self.assertRaises(DocumentNodeLocationError):
                self._resolve(node_ids)
        self.nodes[0]["text"] = ""
        self.results.value = self._result()
        with self.assertRaises(DocumentNodeLocationError):
            self._resolve()

    def test_corrupt_or_noncanonical_result_fails_closed(self):
        good = self._result()
        cases = [replace(good, result_sha256=b"x" * 32)]
        decoded = json.loads(good.content)
        noncanonical = json.dumps(decoded, ensure_ascii=False).encode()
        cases.append(replace(
            good, content=noncanonical,
            result_sha256=hashlib.sha256(noncanonical).digest(),
        ))
        decoded["nodes"][0]["source_locator"] = {
            "locator_type": "PAGE", "page_no": 1,
        }
        malformed = json.dumps(
            decoded, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()
        cases.append(replace(
            good, content=malformed,
            result_sha256=hashlib.sha256(malformed).digest(),
        ))
        for value in cases:
            with self.subTest(value=value.result_sha256), \
                    self.assertRaises(DocumentNodeLocationError):
                self.results.value = value
                self._resolve()

    def test_authorization_error_is_preserved_and_global_path_is_scoped(self):
        self.results.value = ParseResultReadError("AUTH_ACCESS_DENIED")
        with self.assertRaises(DocumentNodeLocationError) as caught:
            self._resolve()
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.query = DocumentReadQuery(
            b"s" * 32, uuid.uuid4(), "GLOBAL", None,
        )
        self.results.value = self._result()
        self.assertEqual(
            self._resolve().content_url,
            f"/api/v1/global/documents/{self.document_id}/versions/"
            f"{self.version_id}/content",
        )

    def test_v1_document_precision_fallback_reauthorizes_fixed_version(self):
        result = self.document_locations.resolve(
            self.query, document_id=self.document_id,
            document_version_id=self.version_id,
        )
        self.assertEqual(result.locator, {"locator_type": "DOCUMENT"})
        self.assertEqual(result.precision, "DOCUMENT")
        self.assertEqual(result.display_label, "整个文档版本")
        self.versions.value = replace(
            self.versions.value, availability_state="REVOKED",
        )
        with self.assertRaises(DocumentNodeLocationError):
            self.document_locations.resolve(
                self.query, document_id=self.document_id,
                document_version_id=self.version_id,
            )
        self.versions.value = DocumentReadError("AUTH_ACCESS_DENIED")
        with self.assertRaises(DocumentNodeLocationError) as caught:
            self.document_locations.resolve(
                self.query, document_id=self.document_id,
                document_version_id=self.version_id,
            )
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")


if __name__ == "__main__":
    import unittest
    unittest.main()
