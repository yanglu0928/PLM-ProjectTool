"""Explicit local-only OCR smoke: synthetic PNG plus native/scanned PDF.

Requires PLM_OCR_DET_MODEL_DIR, PLM_OCR_REC_MODEL_DIR,
PLM_OCR_MODEL_FINGERPRINT and PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True.
No customer files are read and no image is written to disk.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import uuid
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from plm_assistant.modules.parser.application.extract_ocr import extract_ocr
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.infrastructure.paddle_ocr import OfflinePaddleOcr


def _prepared(raw: bytes, mime: str) -> VerifiedParserInput:
    source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(), len(raw), mime)
    return VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(), 1, 1,
                               io.BytesIO(raw))


def main() -> int:
    root_det = Path(os.environ["PLM_OCR_DET_MODEL_DIR"])
    root_rec = Path(os.environ["PLM_OCR_REC_MODEL_DIR"])
    font = Path(os.environ["PLM_OCR_TEST_FONT"])
    adapter = OfflinePaddleOcr(
        detection_model_dir=root_det, recognition_model_dir=root_rec,
        expected_model_fingerprint=os.environ["PLM_OCR_MODEL_FINGERPRINT"],
    )
    image = Image.new("RGB", (1000, 220), "white")
    ImageDraw.Draw(image).text((30, 45), "PROJECT SCOPE APPROVED",
                               font=ImageFont.truetype(str(font), 48), fill="black")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    png = stream.getvalue()
    image_result = extract_ocr(_prepared(png, "image/png"), adapter)
    if (len(image_result.nodes) != 1
            or image_result.nodes[0].text != "PROJECT SCOPE APPROVED"
            or image_result.nodes[0].position.to_locator()["page_no"] != 1):
        raise AssertionError("synthetic image OCR mismatch")

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Native page")
    document.new_page().insert_image(pymupdf.Rect(40, 40, 540, 150), stream=png)
    pdf = document.tobytes()
    document.close()
    pdf_result = extract_ocr(_prepared(pdf, "application/pdf"), adapter)
    if ([node.kind for node in pdf_result.nodes] != ["PDF_TEXT_LINE", "OCR_LINE"]
            or pdf_result.nodes[1].text != "PROJECT SCOPE APPROVED"
            or pdf_result.nodes[1].position.to_locator()["page_no"] != 2):
        raise AssertionError("synthetic mixed PDF OCR mismatch")
    print("PAR-01-A03-P04-P02 synthetic OCR PASS: PNG=1, PDF native=1/OCR=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
