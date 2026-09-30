"""Versioned Parser candidates with reproducible source positions.

These nodes are not Evidence. An authorized resolver must check the fixed
DocumentVersion again before promoting a node to an Evidence reference.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field


_SCHEMA_VERSION = "1"


class ParserResultError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TextRangePosition:
    """Character offsets in NFC text with CRLF/CR normalized to LF."""

    start_offset: int
    end_offset: int
    normalized_fingerprint: str

    def __post_init__(self) -> None:
        if (type(self.start_offset) is not int or self.start_offset < 0
                or type(self.end_offset) is not int or self.end_offset <= self.start_offset
                or type(self.normalized_fingerprint) is not str
                or len(self.normalized_fingerprint) != 64
                or any(char not in "0123456789abcdef" for char in self.normalized_fingerprint)):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "TEXT_RANGE", "section_path": "plain-text-root",
                "start_offset": self.start_offset, "end_offset": self.end_offset,
                "normalized_fingerprint": self.normalized_fingerprint}


@dataclass(frozen=True, slots=True)
class CsvCellPosition:
    row_no: int
    column_no: int

    def __post_init__(self) -> None:
        if (type(self.row_no) is not int or not 1 <= self.row_no <= 1_048_576
                or type(self.column_no) is not int or not 1 <= self.column_no <= 16_384):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        number = self.column_no
        letters = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            letters = chr(65 + remainder) + letters
        cell = f"{letters}{self.row_no}"
        return {"locator_type": "SHEET_RANGE", "sheet_name": "CSV",
                "start_cell": cell, "end_cell": cell}


@dataclass(frozen=True, slots=True)
class ParsedNode:
    node_id: str
    kind: str
    text: str = field(repr=False)
    position: TextRangePosition | CsvCellPosition

    def __post_init__(self) -> None:
        if (type(self.node_id) is not str or not self.node_id
                or len(self.node_id) > 256 or type(self.kind) is not str
                or self.kind not in ("TEXT_LINE", "CSV_CELL")
                or type(self.text) is not str
                or type(self.position) not in (TextRangePosition, CsvCellPosition)
                or (self.kind == "TEXT_LINE") != (type(self.position) is TextRangePosition)):
            raise ParserResultError("PARSER_RESULT_INVALID")

    def to_payload(self) -> dict[str, object]:
        return {"node_id": self.node_id, "kind": self.kind, "text": self.text,
                "source_locator": self.position.to_locator()}


@dataclass(frozen=True, slots=True)
class ParsedResult:
    document_version_id: uuid.UUID
    source_sha256: bytes = field(repr=False)
    parser_profile: str
    parser_version: str
    nodes: tuple[ParsedNode, ...] = field(repr=False)
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (type(self.document_version_id) is not uuid.UUID
                or self.document_version_id.int == 0
                or type(self.source_sha256) is not bytes or len(self.source_sha256) != 32
                or type(self.parser_profile) is not str
                or self.parser_profile not in ("PLAIN_TEXT", "CSV")
                or self.parser_version != "1" or self.schema_version != _SCHEMA_VERSION
                or type(self.nodes) is not tuple
                or any(type(node) is not ParsedNode for node in self.nodes)
                or any((node.kind == "TEXT_LINE") != (self.parser_profile == "PLAIN_TEXT")
                       for node in self.nodes)
                or len({node.node_id for node in self.nodes}) != len(self.nodes)):
            raise ParserResultError("PARSER_RESULT_INVALID")

    def to_payload(self) -> dict[str, object]:
        return {"schema_version": self.schema_version,
                "document_version_id": str(self.document_version_id),
                "source_sha256": self.source_sha256.hex(),
                "parser_profile": self.parser_profile,
                "parser_version": self.parser_version,
                "nodes": [node.to_payload() for node in self.nodes]}

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")

    def result_sha256(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes()).digest()
