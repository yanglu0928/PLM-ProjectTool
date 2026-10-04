from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, ParserProfileError, choose_parser_profile,
)


class ParserProfileSelectionTests(unittest.TestCase):
    def source(self, mime: str = "application/pdf") -> ParserInputVersion:
        return ParserInputVersion(uuid.uuid4(), b"s" * 32, 42, mime)

    def test_supported_content_types_have_versioned_and_source_bound_plans(self) -> None:
        cases = {
            "application/pdf": ("PDF_TEXT_THEN_OCR", "TEXT_FIRST_OCR_IF_NEEDED"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("DOCX", "NONE"),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ("PPTX", "NONE"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("XLSX", "NONE"),
            "text/csv": ("CSV", "NONE"),
            "text/plain": ("PLAIN_TEXT", "NONE"),
            "image/png": ("IMAGE_OCR", "REQUIRED"),
            "image/jpeg": ("IMAGE_OCR", "REQUIRED"),
            "image/tiff": ("IMAGE_OCR", "REQUIRED"),
        }
        for mime, expected in cases.items():
            with self.subTest(mime=mime):
                source = self.source(mime)
                plan = choose_parser_profile(source)
                self.assertIs(plan.source, source)
                self.assertEqual((plan.parser_profile, plan.ocr_policy), expected)
                self.assertEqual(plan.parser_version, "2" if plan.parser_profile == "DOCX" else "1")
                self.assertIsInstance(plan.component_order, tuple)
                self.assertGreater(len(plan.component_order), 0)
        self.assertEqual(choose_parser_profile(self.source("image/png")).component_order[0], "PaddleOCR")
        self.assertEqual(choose_parser_profile(self.source()).component_order[0], "PyMuPDF")

    def test_invalid_version_hash_size_and_mime_fail_closed(self) -> None:
        cases = [
            (uuid.UUID(int=0), b"s" * 32, 1, "application/pdf"),
            (str(uuid.uuid4()), b"s" * 32, 1, "application/pdf"),
            (uuid.uuid4(), b"short", 1, "application/pdf"),
            (uuid.uuid4(), bytearray(b"s" * 32), 1, "application/pdf"),
            (uuid.uuid4(), b"s" * 32, -1, "application/pdf"),
            (uuid.uuid4(), b"s" * 32, 100_000_001, "application/pdf"),
            (uuid.uuid4(), b"s" * 32, True, "application/pdf"),
            (uuid.uuid4(), b"s" * 32, 1, " application/pdf"),
            (uuid.uuid4(), b"s" * 32, 1, ""),
        ]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(ParserProfileError) as error:
                    ParserInputVersion(*args)
                self.assertEqual(error.exception.code, "PARSER_INPUT_INVALID")
        with self.assertRaises(ParserProfileError):
            choose_parser_profile(object())

    def test_unrecognized_and_caller_modified_mime_never_falls_back(self) -> None:
        for mime in ("application/octet-stream", "APPLICATION/PDF", "application/pdf; charset=utf-8", "image/svg+xml"):
            with self.subTest(mime=mime):
                with self.assertRaises(ParserProfileError) as error:
                    choose_parser_profile(self.source(mime))
                self.assertEqual(error.exception.code, "PARSER_FORMAT_UNSUPPORTED")
        source = self.source()
        object.__setattr__(source, "content_sha256", b"bad")
        with self.assertRaises(ParserProfileError):
            choose_parser_profile(source)


if __name__ == "__main__":
    unittest.main()
