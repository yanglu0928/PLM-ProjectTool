"""Native PDF text candidates; image-only pages require a separate OCR pass."""

from __future__ import annotations

import hashlib
import hmac
import unicodedata

import pymupdf

from .prepare_input import VerifiedParserInput
from .profile_selection import choose_parser_profile
from .structured_result import (
    ParsedNode, ParsedResult, ParserResultError, PdfTextRangePosition,
)


_MAX_PAGES = 1_000
_MAX_CHARS = 32_000_000
_MAX_NODES = 100_000


def extract_pdf_text(prepared: VerifiedParserInput) -> ParsedResult:
    if type(prepared) is not VerifiedParserInput:
        raise ParserResultError("PARSER_INPUT_INVALID")
    plan = prepared.plan
    if (plan != choose_parser_profile(plan.source)
            or plan.parser_profile != "PDF_TEXT_THEN_OCR"):
        raise ParserResultError("PARSER_FORMAT_UNSUPPORTED")
    try:
        prepared.stream.seek(0)
        raw = prepared.stream.read(plan.source.size_bytes + 1)
    except (OSError, ValueError, AttributeError):
        raise ParserResultError("PARSER_INPUT_UNAVAILABLE") from None
    if (type(raw) is not bytes or len(raw) != plan.source.size_bytes
            or not hmac.compare_digest(hashlib.sha256(raw).digest(),
                                       plan.source.content_sha256)):
        raise ParserResultError("FILE_INTEGRITY_MISMATCH")
    nodes: list[ParsedNode] = []
    total_chars = 0
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as document:
            if document.is_encrypted:
                raise ParserResultError("PARSER_PDF_ENCRYPTED")
            if not 1 <= document.page_count <= _MAX_PAGES:
                raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
            for page_no, page in enumerate(document, 1):
                page_nodes, page_chars = native_pdf_page_nodes(page, page_no)
                total_chars += page_chars
                if total_chars > _MAX_CHARS:
                    raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
                if not page_nodes:
                    raise ParserResultError("PARSER_OCR_REQUIRED")
                nodes.extend(page_nodes)
                if len(nodes) > _MAX_NODES:
                    raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
    except ParserResultError:
        raise
    except Exception:
        raise ParserResultError("PARSER_PDF_INVALID") from None
    return ParsedResult(plan.source.document_version_id, plan.source.content_sha256,
                        plan.parser_profile, plan.parser_version, tuple(nodes))


def native_pdf_page_nodes(page: pymupdf.Page, page_no: int
                          ) -> tuple[tuple[ParsedNode, ...], int]:
    """Return exact line offsets in this page's versioned PyMuPDF text view."""
    source_text = page.get_text("text", sort=True)
    if type(source_text) is not str:
        raise ParserResultError("PARSER_PDF_INVALID")
    text = unicodedata.normalize(
        "NFC", source_text.replace("\r\n", "\n").replace("\r", "\n"))
    nodes: list[ParsedNode] = []
    offset = 0
    for line_no, value in enumerate(text.split("\n"), 1):
        if value.strip():
            fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()
            nodes.append(ParsedNode(
                f"page:{page_no}:line:{line_no}", "PDF_TEXT_LINE", value,
                PdfTextRangePosition(page_no, offset, offset + len(value), fingerprint)))
        offset += len(value) + 1
    return tuple(nodes), len(text)
