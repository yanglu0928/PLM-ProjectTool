from __future__ import annotations

import hashlib
import io
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.evidence.domain.locator import validate_evidence_locator
from plm_assistant.modules.parser.application.extract_textual import extract_textual
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.structured_result import ParserResultError


class ExtractTextualTests(unittest.TestCase):
    def prepared(self, raw: bytes, mime: str) -> VerifiedParserInput:
        source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(), len(raw), mime)
        return VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(), 1, 1,
                                   io.BytesIO(raw))

    def test_chinese_bom_crlf_and_replayable_text_ranges(self) -> None:
        prepared = self.prepared(b"\xef\xbb\xbf" + "甲\r\n\r乙\n".encode(), "text/plain")
        parsed = extract_textual(prepared)
        self.assertEqual([node.text for node in parsed.nodes], ["甲", "乙"])
        self.assertEqual([node.node_id for node in parsed.nodes], ["line:1", "line:3"])
        normalized = "甲\n\n乙\n"
        for node in parsed.nodes:
            locator = node.position.to_locator()
            self.assertEqual(validate_evidence_locator(locator), locator)
            selected = normalized[locator["start_offset"]:locator["end_offset"]]
            self.assertEqual(selected, node.text)
            self.assertEqual(hashlib.sha256(selected.encode()).hexdigest(),
                             locator["normalized_fingerprint"])
        self.assertEqual(parsed.canonical_bytes(), extract_textual(prepared).canonical_bytes())
        self.assertEqual(hashlib.sha256(parsed.canonical_bytes()).digest(),
                         parsed.result_sha256())

    def test_csv_quoted_newline_unicode_and_empty_cells_have_exact_a1_positions(self) -> None:
        prepared = self.prepared("名称,备注\r\n测试,\"多行\n内容\"\r\n,尾列\r\n".encode(), "text/csv")
        parsed = extract_textual(prepared)
        self.assertEqual([node.text for node in parsed.nodes],
                         ["名称", "备注", "测试", "多行\n内容", "", "尾列"])
        self.assertEqual([node.position.to_locator()["start_cell"] for node in parsed.nodes],
                         ["A1", "B1", "A2", "B2", "A3", "B3"])
        for node in parsed.nodes:
            self.assertEqual(validate_evidence_locator(node.position.to_locator()),
                             node.position.to_locator())
        self.assertEqual(parsed.nodes[3].position.to_locator()["sheet_name"], "CSV")
        self.assertEqual(parsed.canonical_bytes(), extract_textual(prepared).canonical_bytes())

    def test_rejects_wrong_profile_integrity_encoding_and_malformed_csv(self) -> None:
        prepared = self.prepared(b"hello", "text/plain")
        prepared.stream = io.BytesIO(b"hullo")
        with self.assertRaises(ParserResultError) as error:
            extract_textual(prepared)
        self.assertEqual(error.exception.code, "FILE_INTEGRITY_MISMATCH")
        prepared = self.prepared(b"\xff", "text/plain")
        with self.assertRaises(ParserResultError) as error:
            extract_textual(prepared)
        self.assertEqual(error.exception.code, "PARSER_TEXT_ENCODING_INVALID")
        prepared = self.prepared(b'"unterminated', "text/csv")
        with self.assertRaises(ParserResultError) as error:
            extract_textual(prepared)
        self.assertEqual(error.exception.code, "PARSER_CSV_INVALID")
        prepared = self.prepared(b"%PDF", "application/pdf")
        with self.assertRaises(ParserResultError) as error:
            extract_textual(prepared)
        self.assertEqual(error.exception.code, "PARSER_FORMAT_UNSUPPORTED")

    def test_no_partial_result_on_output_limit_or_forged_plan(self) -> None:
        prepared = self.prepared(b"a\x00b", "text/plain")
        with self.assertRaises(ParserResultError) as error:
            extract_textual(prepared)
        self.assertEqual(error.exception.code, "PARSER_RESULT_LIMIT_EXCEEDED")
        prepared = self.prepared(b"abc", "text/plain")
        prepared.plan = replace(prepared.plan, parser_version="unapproved")
        with self.assertRaises(ParserResultError) as error:
            extract_textual(prepared)
        self.assertEqual(error.exception.code, "PARSER_FORMAT_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
