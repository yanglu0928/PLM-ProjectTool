"""Real offline-model OCR on disposable synthetic PNG and scanned PDF files."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult
from plm_assistant.modules.evidence.application.parsed_node_proof import ParsedNodeEvidenceProofService
from plm_assistant.modules.parser.application.extract_ocr import extract_ocr
from plm_assistant.modules.parser.application.prepare_input import VerifiedParserInput
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.infrastructure.paddle_ocr import (
    OfflinePaddleOcr, _model_fingerprint,
)


TEXT = "PROJECT SCOPE APPROVED"
IMAGE_SIZE = (1000, 220)
PDF_IMAGE_RECT = pymupdf.Rect(40, 40, 540, 150)


class ResultPort:
    def __init__(self, value: VerifiedParseResult) -> None:
        self.value = value

    def read(self, *_args, **_kwargs) -> VerifiedParseResult:
        return self.value


def make_image(path: Path, font_path: Path) -> tuple[float, float, float, float]:
    image = Image.new("RGB", IMAGE_SIZE, "white")
    drawer = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 48)
    drawn = drawer.textbbox((30, 45), TEXT, font=font)
    drawer.text((30, 45), TEXT, font=font, fill="black")
    image.save(path, format="PNG")
    return (drawn[0] / IMAGE_SIZE[0], drawn[1] / IMAGE_SIZE[1],
            drawn[2] / IMAGE_SIZE[0], drawn[3] / IMAGE_SIZE[1])


def make_pdf(path: Path, image_path: Path) -> None:
    with pymupdf.open() as document:
        document.new_page().insert_image(PDF_IMAGE_RECT, stream=image_path.read_bytes())
        document.save(path)


def parse_file(path: Path, mime: str, engine: OfflinePaddleOcr):
    raw = path.read_bytes()
    source = ParserInputVersion(uuid.uuid4(), hashlib.sha256(raw).digest(), len(raw), mime)
    with path.open("rb") as stream:
        prepared = VerifiedParserInput(choose_parser_profile(source), uuid.uuid4(), 1, 1,
                                       stream)
        parsed = extract_ocr(prepared, engine)
    assert parsed.source_sha256 == source.content_sha256
    assert parsed.ocr_model_fingerprint == engine.model_fingerprint
    return source, parsed


def intersects(a: tuple[float, float, float, float],
               b: tuple[float, float, float, float]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def prove(source: ParserInputVersion, parsed) -> None:
    content = parsed.canonical_bytes()
    record_id, document_id = uuid.uuid4(), uuid.uuid4()
    result = VerifiedParseResult(
        record_id, source.document_version_id, uuid.uuid4(),
        parsed.parser_profile, parsed.parser_version, source.content_sha256,
        hashlib.sha256(content).digest(), content,
    )
    proof = ParsedNodeEvidenceProofService(results=ResultPort(result))
    query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", uuid.uuid4())
    for node in parsed.nodes:
        locator = node.position.to_locator()
        direct = proof.prove(query, document_id=document_id,
                             document_version_id=source.document_version_id,
                             parse_record_id=record_id, locator=locator)
        assert direct.node_id == node.node_id
        assert direct.content_fingerprint == hashlib.sha256(node.text.encode()).digest()
        structured = {"locator_type": "STRUCTURED_NODE",
                      "parse_record_id": str(record_id), "node_id": node.node_id,
                      "source_locator": locator}
        assert proof.prove(query, document_id=document_id,
                           document_version_id=source.document_version_id,
                           parse_record_id=record_id, locator=structured).node_id == node.node_id


def verify_image(path: Path, font: Path, engine: OfflinePaddleOcr) -> None:
    drawn = make_image(path, font)
    source, parsed = parse_file(path, "image/png", engine)
    assert parsed.parser_profile == "IMAGE_OCR"
    matches = [node for node in parsed.nodes if node.kind == "OCR_LINE" and node.text == TEXT]
    assert len(matches) == 1, [(node.kind, node.text) for node in parsed.nodes]
    locator = matches[0].position.to_locator()
    assert locator["locator_type"] == "PAGE" and locator["page_no"] == 1
    assert intersects(tuple(locator["bbox"]), drawn)
    prove(source, parsed)


def verify_scanned_pdf(path: Path, image_path: Path,
                       engine: OfflinePaddleOcr) -> None:
    make_pdf(path, image_path)
    with pymupdf.open(path) as reopened:
        assert not reopened[0].get_text("text").strip()
        page_rect = reopened[0].rect
        drawn_region = (PDF_IMAGE_RECT.x0 / page_rect.width,
                        PDF_IMAGE_RECT.y0 / page_rect.height,
                        PDF_IMAGE_RECT.x1 / page_rect.width,
                        PDF_IMAGE_RECT.y1 / page_rect.height)
    source, parsed = parse_file(path, "application/pdf", engine)
    assert parsed.parser_profile == "PDF_TEXT_THEN_OCR"
    matches = [node for node in parsed.nodes if node.kind == "OCR_LINE" and node.text == TEXT]
    assert len(matches) == 1, [(node.kind, node.text) for node in parsed.nodes]
    locator = matches[0].position.to_locator()
    assert locator["locator_type"] == "PAGE" and locator["page_no"] == 1
    assert intersects(tuple(locator["bbox"]), drawn_region)
    prove(source, parsed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--det", type=Path, required=True)
    parser.add_argument("--rec", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    if not args.font.is_file():
        raise RuntimeError("font missing")
    with tempfile.TemporaryDirectory(prefix="plm-evd-real-ocr-") as scratch:
        root = Path(scratch)
        if not str(root).isascii():
            raise RuntimeError("temporary model path must be ASCII on Windows")
        det, rec = root / "det", root / "rec"
        shutil.copytree(args.det, det)
        shutil.copytree(args.rec, rec)
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        engine = OfflinePaddleOcr(
            detection_model_dir=det, recognition_model_dir=rec,
            expected_model_fingerprint=_model_fingerprint(det, rec),
        )
        image_path = root / "synthetic.png"
        verify_image(image_path, args.font, engine)
        verify_scanned_pdf(root / "scanned.pdf", image_path, engine)
    print("PASS: local offline model recognized synthetic PNG and scanned PDF; "
          "PAGE boxes intersect known content and Evidence proves fixed nodes")


if __name__ == "__main__":
    main()
