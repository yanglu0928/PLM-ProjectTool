from __future__ import annotations

import hashlib
import io
import unittest
import uuid

import numpy as np
import pymupdf
from PIL import Image

from plm_assistant.modules.evidence.domain.locator import validate_evidence_locator
from plm_assistant.modules.parser.application.extract_ocr import extract_ocr
from plm_assistant.modules.parser.application.ocr_contract import OcrLine
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.structured_result import ParserResultError


class _Engine:
    model_fingerprint = "a" * 64

    def __init__(self, lines=None) -> None:
        self.lines = (OcrLine("扫描结论", 0.91, (0.1, 0.2, 0.8, 0.4)),) if lines is None else lines
        self.calls: list[tuple[int, int, int]] = []

    def recognize(self, image: np.ndarray) -> tuple[OcrLine, ...]:
        self.calls.append(image.shape)
        return self.lines


class ExtractOcrTests(unittest.TestCase):
    def prepared(self, raw: bytes, mime: str) -> VerifiedParserInput:
        source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(),
                                    len(raw), mime)
        return VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(), 1, 1,
                                   io.BytesIO(raw))

    def image_bytes(self, kind="PNG", *, pages=1) -> bytes:
        images = [Image.new("RGB", (300, 120), "white") for _ in range(pages)]
        stream = io.BytesIO()
        if kind == "TIFF":
            images[0].save(stream, format="TIFF", save_all=True,
                           append_images=images[1:])
        else:
            images[0].save(stream, format=kind)
        return stream.getvalue()

    def test_png_and_multiframe_tiff_page_boxes_are_typed_and_deterministic(self) -> None:
        for kind, mime, pages in (("PNG", "image/png", 1),
                                  ("TIFF", "image/tiff", 2)):
            with self.subTest(kind=kind):
                prepared = self.prepared(self.image_bytes(kind, pages=pages), mime)
                engine = _Engine()
                parsed = extract_ocr(prepared, engine)
                self.assertEqual(len(parsed.nodes), pages)
                self.assertEqual([node.position.page_no for node in parsed.nodes],
                                 list(range(1, pages + 1)))
                self.assertEqual(parsed.ocr_model_fingerprint, engine.model_fingerprint)
                self.assertEqual([node.confidence for node in parsed.nodes], [0.91] * pages)
                for node in parsed.nodes:
                    locator = node.position.to_locator()
                    self.assertEqual(validate_evidence_locator(locator), locator)
                self.assertEqual(parsed.canonical_bytes(),
                                 extract_ocr(prepared, _Engine()).canonical_bytes())

    def test_mixed_pdf_keeps_native_text_and_only_ocr_on_scanned_page(self) -> None:
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Native first page")
        page = document.new_page()
        page.insert_image(pymupdf.Rect(10, 10, 310, 130),
                          stream=self.image_bytes())
        prepared = self.prepared(document.tobytes(), "application/pdf")
        document.close()
        engine = _Engine()
        parsed = extract_ocr(prepared, engine)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual([node.kind for node in parsed.nodes],
                         ["PDF_TEXT_LINE", "OCR_LINE"])
        self.assertEqual(parsed.nodes[0].position.to_locator()["page_no"], 1)
        self.assertEqual(parsed.nodes[1].position.to_locator()["page_no"], 2)

    def test_no_text_orientation_mismatch_and_tamper_fail_closed(self) -> None:
        prepared = self.prepared(self.image_bytes(), "image/png")
        with self.assertRaises(ParserResultError) as error:
            extract_ocr(prepared, _Engine(lines=()))
        self.assertEqual(error.exception.code, "PARSER_OCR_NO_TEXT")
        prepared = self.prepared(self.image_bytes(), "image/png")
        prepared.stream = io.BytesIO(b"tampered")
        with self.assertRaises(ParserResultError) as error:
            extract_ocr(prepared, _Engine())
        self.assertEqual(error.exception.code, "FILE_INTEGRITY_MISMATCH")
        image = Image.new("RGB", (300, 120), "white")
        exif = image.getexif()
        exif[274] = 6
        stream = io.BytesIO()
        image.save(stream, format="JPEG", exif=exif)
        with self.assertRaises(ParserResultError) as error:
            extract_ocr(self.prepared(stream.getvalue(), "image/jpeg"), _Engine())
        self.assertEqual(error.exception.code, "PARSER_IMAGE_ORIENTATION_UNSUPPORTED")

    def test_mime_mismatch_is_not_accepted(self) -> None:
        prepared = self.prepared(self.image_bytes("PNG"), "image/jpeg")
        with self.assertRaises(ParserResultError) as error:
            extract_ocr(prepared, _Engine())
        self.assertEqual(error.exception.code, "PARSER_IMAGE_INVALID")


if __name__ == "__main__":
    unittest.main()
