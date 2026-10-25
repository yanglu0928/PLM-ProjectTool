"""Image and mixed-PDF OCR candidates from a verified immutable snapshot."""

from __future__ import annotations

import hashlib
import hmac
import io

import numpy as np
import pymupdf
from PIL import Image, UnidentifiedImageError

from .extract_pdf_text import native_pdf_page_nodes
from .ocr_contract import OcrEnginePort, OcrLine, OcrResultError
from .prepare_input import VerifiedParserInput
from .profile_selection import choose_parser_profile
from .structured_result import PageBoxPosition, ParsedNode, ParsedResult, ParserResultError


_MAX_PAGES = 1_000
_MAX_IMAGE_PIXELS = 20_000_000
_MAX_TOTAL_RENDER_PIXELS = 100_000_000
_MAX_CHARS = 32_000_000
_MAX_NODES = 100_000
_PDF_RENDER_SCALE = 2.0
_IMAGE_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/tiff": "TIFF"}


def extract_ocr(prepared: VerifiedParserInput, engine: OcrEnginePort) -> ParsedResult:
    if type(prepared) is not VerifiedParserInput:
        raise ParserResultError("PARSER_INPUT_INVALID")
    plan = prepared.plan
    if (plan != choose_parser_profile(plan.source)
            or plan.parser_profile not in ("IMAGE_OCR", "PDF_TEXT_THEN_OCR")):
        raise ParserResultError("PARSER_FORMAT_UNSUPPORTED")
    fingerprint = getattr(engine, "model_fingerprint", None)
    if (type(fingerprint) is not str or len(fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in fingerprint)
            or not callable(getattr(engine, "recognize", None))):
        raise ParserResultError("PARSER_OCR_ENGINE_INVALID")
    try:
        prepared.stream.seek(0)
        raw = prepared.stream.read(plan.source.size_bytes + 1)
    except (OSError, ValueError, AttributeError):
        raise ParserResultError("PARSER_INPUT_UNAVAILABLE") from None
    if (type(raw) is not bytes or len(raw) != plan.source.size_bytes
            or not hmac.compare_digest(hashlib.sha256(raw).digest(),
                                       plan.source.content_sha256)):
        raise ParserResultError("FILE_INTEGRITY_MISMATCH")
    if plan.parser_profile == "IMAGE_OCR":
        nodes = _image_nodes(raw, plan.source.detected_mime, engine)
    else:
        nodes = _pdf_nodes(raw, engine)
    return ParsedResult(plan.source.document_version_id, plan.source.content_sha256,
                        plan.parser_profile, plan.parser_version, tuple(nodes),
                        ocr_model_fingerprint=fingerprint if any(
                            node.kind == "OCR_LINE" for node in nodes) else None)


def _image_nodes(raw: bytes, mime: str, engine: OcrEnginePort) -> list[ParsedNode]:
    nodes: list[ParsedNode] = []
    total_chars = 0
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format != _IMAGE_FORMATS[mime]:
                raise ParserResultError("PARSER_IMAGE_INVALID")
            page_count = getattr(source, "n_frames", 1)
            if not 1 <= page_count <= _MAX_PAGES:
                raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
            total_pixels = 0
            for page_no in range(1, page_count + 1):
                source.seek(page_no - 1)
                if source.getexif().get(274, 1) != 1:
                    raise ParserResultError("PARSER_IMAGE_ORIENTATION_UNSUPPORTED")
                width, height = source.size
                pixels = width * height
                total_pixels += pixels
                if (not 1 <= pixels <= _MAX_IMAGE_PIXELS
                        or total_pixels > _MAX_TOTAL_RENDER_PIXELS):
                    raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
                image = np.asarray(source.convert("RGB"))
                new_nodes = _ocr_page_nodes(image, page_no, engine)
                nodes.extend(new_nodes)
                total_chars += sum(len(node.text) for node in new_nodes)
                _check_output(nodes, total_chars)
    except ParserResultError:
        raise
    except (OSError, ValueError, UnidentifiedImageError):
        raise ParserResultError("PARSER_IMAGE_INVALID") from None
    return nodes


def _pdf_nodes(raw: bytes, engine: OcrEnginePort) -> list[ParsedNode]:
    nodes: list[ParsedNode] = []
    total_chars = total_pixels = 0
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as document:
            if document.is_encrypted:
                raise ParserResultError("PARSER_PDF_ENCRYPTED")
            if not 1 <= document.page_count <= _MAX_PAGES:
                raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
            for page_no, page in enumerate(document, 1):
                native_nodes, page_chars = native_pdf_page_nodes(page, page_no)
                total_chars += page_chars
                if total_chars > _MAX_CHARS:
                    raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
                if native_nodes:
                    nodes.extend(native_nodes)
                else:
                    width = round(page.rect.width * _PDF_RENDER_SCALE)
                    height = round(page.rect.height * _PDF_RENDER_SCALE)
                    pixels = width * height
                    total_pixels += pixels
                    if (not 1 <= pixels <= _MAX_IMAGE_PIXELS
                            or total_pixels > _MAX_TOTAL_RENDER_PIXELS):
                        raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(_PDF_RENDER_SCALE,
                                                                 _PDF_RENDER_SCALE),
                                          colorspace=pymupdf.csRGB, alpha=False)
                    if pix.width * pix.height > _MAX_IMAGE_PIXELS:
                        raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
                    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, 3).copy()
                    new_nodes = _ocr_page_nodes(image, page_no, engine)
                    nodes.extend(new_nodes)
                    total_chars += sum(len(node.text) for node in new_nodes)
                _check_output(nodes, total_chars)
    except ParserResultError:
        raise
    except Exception:
        raise ParserResultError("PARSER_PDF_INVALID") from None
    return nodes


def _ocr_page_nodes(image: np.ndarray, page_no: int,
                    engine: OcrEnginePort) -> list[ParsedNode]:
    try:
        lines = engine.recognize(image)
    except Exception:
        raise ParserResultError("PARSER_OCR_FAILED") from None
    if type(lines) is not tuple or not lines:
        raise ParserResultError("PARSER_OCR_NO_TEXT")
    nodes: list[ParsedNode] = []
    for index, line in enumerate(lines, 1):
        if type(line) is not OcrLine:
            raise ParserResultError("PARSER_OCR_RESULT_INVALID")
        try:
            line.__post_init__()
        except OcrResultError:
            raise ParserResultError("PARSER_OCR_RESULT_INVALID") from None
        nodes.append(ParsedNode(f"page:{page_no}:ocr:{index}", "OCR_LINE",
                                line.text, PageBoxPosition(page_no, line.bbox),
                                line.confidence))
    return nodes


def _check_output(nodes: list[ParsedNode], total_chars: int) -> None:
    if len(nodes) > _MAX_NODES or total_chars > _MAX_CHARS:
        raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
