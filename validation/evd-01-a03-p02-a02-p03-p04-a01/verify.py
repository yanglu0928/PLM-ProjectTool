"""Real local OCR for a synthetic mixed native-text and Chinese scanned PDF."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from plm_assistant.modules.parser.infrastructure.paddle_ocr import (
    OfflinePaddleOcr, _model_fingerprint,
)


PREVIOUS = Path(__file__).resolve().parents[1] / "evd-01-a03-p02-a02-p03-p03-p02" / "verify.py"
SPEC = spec_from_file_location("evd_real_ocr", PREVIOUS)
assert SPEC is not None and SPEC.loader is not None
HELPER = module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)

CHINESE_TEXT = "项目范围已确认"
IMAGE_RECT = pymupdf.Rect(40, 40, 540, 150)


def make_scanned_image(path: Path, font_path: Path) -> None:
    image = Image.new("RGB", (1000, 220), "white")
    drawer = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 64)
    drawer.text((30, 45), CHINESE_TEXT, font=font, fill="black")
    image.save(path, format="PNG")


def make_mixed_pdf(path: Path, image_path: Path) -> None:
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Native scope approved")
        document.new_page().insert_image(IMAGE_RECT, stream=image_path.read_bytes())
        document.save(path)


def verify(path: Path, image_path: Path, engine: OfflinePaddleOcr) -> None:
    make_mixed_pdf(path, image_path)
    with pymupdf.open(path) as reopened:
        assert reopened.page_count == 2
        assert "Native scope approved" in reopened[0].get_text("text")
        assert not reopened[1].get_text("text").strip()
        page_rect = reopened[1].rect
        image_region = (IMAGE_RECT.x0 / page_rect.width,
                        IMAGE_RECT.y0 / page_rect.height,
                        IMAGE_RECT.x1 / page_rect.width,
                        IMAGE_RECT.y1 / page_rect.height)
    source, parsed = HELPER.parse_file(path, "application/pdf", engine)
    assert parsed.parser_profile == "PDF_TEXT_THEN_OCR"
    native = [node for node in parsed.nodes if node.kind == "PDF_TEXT_LINE"]
    chinese = [node for node in parsed.nodes if node.kind == "OCR_LINE"]
    assert len(native) == 1 and native[0].text == "Native scope approved"
    assert native[0].position.to_locator()["page_no"] == 1
    matches = [node for node in chinese if node.text == CHINESE_TEXT]
    assert len(matches) == 1, [(node.kind, node.text) for node in parsed.nodes]
    locator = matches[0].position.to_locator()
    assert locator["locator_type"] == "PAGE" and locator["page_no"] == 2
    assert HELPER.intersects(tuple(locator["bbox"]), image_region)
    HELPER.prove(source, parsed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--det", type=Path, required=True)
    parser.add_argument("--rec", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    if not args.font.is_file():
        raise RuntimeError("Chinese font missing")
    with tempfile.TemporaryDirectory(prefix="plm-evd-chinese-mixed-pdf-") as scratch:
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
        image_path = root / "chinese.png"
        make_scanned_image(image_path, args.font)
        verify(root / "mixed.pdf", image_path, engine)
    print("PASS: two-page PDF kept native page 1 and real Chinese OCR page 2 separate; "
          "locators and Evidence proof matched synthetic source")


if __name__ == "__main__":
    main()
