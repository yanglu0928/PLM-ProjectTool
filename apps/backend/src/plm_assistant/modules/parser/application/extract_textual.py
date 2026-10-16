"""Deterministic UTF-8 plain-text and comma-separated Parser extraction."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import unicodedata

from .prepare_input import VerifiedParserInput
from .profile_selection import choose_parser_profile
from .structured_result import (
    CsvCellPosition, ParsedNode, ParsedResult, ParserResultError, TextRangePosition,
)


_MAX_CHARS = 32_000_000
_MAX_NODES = 100_000


def extract_textual(prepared: VerifiedParserInput) -> ParsedResult:
    """Extract candidates from a previously fenced, verified private snapshot.

    This is CPU-only. The caller retains the stream and must recheck its Job
    fencing token before publishing any result.
    """
    if type(prepared) is not VerifiedParserInput:
        raise ParserResultError("PARSER_INPUT_INVALID")
    plan = prepared.plan
    if (plan != choose_parser_profile(plan.source)
            or plan.parser_profile not in ("PLAIN_TEXT", "CSV")):
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
    try:
        decoded = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ParserResultError("PARSER_TEXT_ENCODING_INVALID") from None
    if len(decoded) > _MAX_CHARS or "\x00" in decoded:
        raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
    if plan.parser_profile == "PLAIN_TEXT":
        nodes = _text_nodes(decoded)
    else:
        nodes = _csv_nodes(decoded)
    return ParsedResult(plan.source.document_version_id, plan.source.content_sha256,
                        plan.parser_profile, plan.parser_version, nodes)


def _text_nodes(decoded: str) -> tuple[ParsedNode, ...]:
    text = unicodedata.normalize("NFC", decoded.replace("\r\n", "\n").replace("\r", "\n"))
    nodes: list[ParsedNode] = []
    offset = 0
    for line_no, value in enumerate(text.split("\n"), 1):
        if value:
            fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()
            nodes.append(ParsedNode(f"line:{line_no}", "TEXT_LINE", value,
                                    TextRangePosition(offset, offset + len(value), fingerprint)))
            if len(nodes) > _MAX_NODES:
                raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
        offset += len(value) + 1
    return tuple(nodes)


def _csv_nodes(decoded: str) -> tuple[ParsedNode, ...]:
    nodes: list[ParsedNode] = []
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        for row_no, row in enumerate(reader, 1):
            if row_no > 1_048_576 or len(row) > 16_384:
                raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
            for column_no, value in enumerate(row, 1):
                nodes.append(ParsedNode(f"r{row_no}c{column_no}", "CSV_CELL", value,
                                        CsvCellPosition(row_no, column_no)))
                if len(nodes) > _MAX_NODES:
                    raise ParserResultError("PARSER_RESULT_LIMIT_EXCEEDED")
    except csv.Error:
        raise ParserResultError("PARSER_CSV_INVALID") from None
    return tuple(nodes)
