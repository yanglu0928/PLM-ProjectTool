from __future__ import annotations

import hashlib
import io
import unittest
import uuid

import pymupdf

from plm_assistant.modules.evidence.domain.locator import validate_evidence_locator
from plm_assistant.modules.parser.application.extract_pdf_text import extract_pdf_text
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.structured_result import ParserResultError


class ExtractPdfTextTests(unittest.TestCase):
    def prepared(self, raw: bytes) -> VerifiedParserInput:
        source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(),
                                    len(raw), "application/pdf")
        return VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(), 1, 1,
                                   io.BytesIO(raw))

    def test_native_two_page_text_has_replayable_page_ranges(self) -> None:
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Scope A\nDecision B")
        document.new_page().insert_text((72, 72), "Scope C")
        prepared = self.prepared(document.tobytes())
        document.close()
        parsed = extract_pdf_text(prepared)
        self.assertEqual([node.text for node in parsed.nodes],
                         ["Scope A", "Decision B", "Scope C"])
        self.assertEqual([node.position.page_no for node in parsed.nodes], [1, 1, 2])
        with pymupdf.open(stream=prepared.stream.getvalue(), filetype="pdf") as document:
            for node in parsed.nodes:
                locator = node.position.to_locator()
                self.assertEqual(validate_evidence_locator(locator), locator)
                page_text = document[locator["page_no"] - 1].get_text("text", sort=True)
                selected = page_text[locator["start_offset"]:locator["end_offset"]]
                self.assertEqual(selected, node.text)
                self.assertEqual(hashlib.sha256(selected.encode()).hexdigest(),
                                 locator["normalized_fingerprint"])
        self.assertEqual(parsed.canonical_bytes(), extract_pdf_text(prepared).canonical_bytes())

    def test_blank_or_mixed_page_requires_ocr_without_partial_success(self) -> None:
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "native")
        document.new_page()
        prepared = self.prepared(document.tobytes())
        document.close()
        with self.assertRaises(ParserResultError) as error:
            extract_pdf_text(prepared)
        self.assertEqual(error.exception.code, "PARSER_OCR_REQUIRED")

    def test_corruption_and_mutated_snapshot_fail_closed(self) -> None:
        prepared = self.prepared(b"not a PDF")
        with self.assertRaises(ParserResultError) as error:
            extract_pdf_text(prepared)
        self.assertEqual(error.exception.code, "PARSER_PDF_INVALID")
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "native")
        prepared = self.prepared(document.tobytes())
        document.close()
        prepared.stream = io.BytesIO(b"tampered")
        with self.assertRaises(ParserResultError) as error:
            extract_pdf_text(prepared)
        self.assertEqual(error.exception.code, "FILE_INTEGRITY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
