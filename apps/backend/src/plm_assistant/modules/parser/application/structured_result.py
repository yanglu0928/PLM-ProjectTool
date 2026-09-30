"""Versioned Parser candidates with reproducible source positions.

These nodes are not Evidence. An authorized resolver must check the fixed
DocumentVersion again before promoting a node to an Evidence reference.
"""

from __future__ import annotations

import hashlib
import json
import math
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
class PdfTextRangePosition:
    page_no: int
    start_offset: int
    end_offset: int
    normalized_fingerprint: str

    def __post_init__(self) -> None:
        if (type(self.page_no) is not int or self.page_no <= 0
                or type(self.start_offset) is not int or self.start_offset < 0
                or type(self.end_offset) is not int or self.end_offset <= self.start_offset
                or type(self.normalized_fingerprint) is not str
                or len(self.normalized_fingerprint) != 64
                or any(char not in "0123456789abcdef" for char in self.normalized_fingerprint)):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "TEXT_RANGE", "page_no": self.page_no,
                "start_offset": self.start_offset, "end_offset": self.end_offset,
                "normalized_fingerprint": self.normalized_fingerprint}


@dataclass(frozen=True, slots=True)
class PageBoxPosition:
    page_no: int
    bbox: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if (type(self.page_no) is not int or self.page_no <= 0
                or type(self.bbox) is not tuple or len(self.bbox) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or not 0 <= value <= 1 for value in self.bbox)
                or self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "PAGE", "page_no": self.page_no,
                "bbox": list(self.bbox)}


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
class ParagraphPosition:
    paragraph_index: int

    def __post_init__(self) -> None:
        if type(self.paragraph_index) is not int or self.paragraph_index <= 0:
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "PARAGRAPH", "paragraph_index": self.paragraph_index}


@dataclass(frozen=True, slots=True)
class TableCellPosition:
    table_anchor: str
    row_no: int
    column_no: int

    def __post_init__(self) -> None:
        if (type(self.table_anchor) is not str or not self.table_anchor
                or len(self.table_anchor) > 256
                or type(self.row_no) is not int or self.row_no <= 0
                or type(self.column_no) is not int or self.column_no <= 0):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "TABLE_CELL", "table_anchor": self.table_anchor,
                "row_no": self.row_no, "column_no": self.column_no}


@dataclass(frozen=True, slots=True)
class SlideShapePosition:
    slide_no: int
    shape_id: str

    def __post_init__(self) -> None:
        if (type(self.slide_no) is not int or self.slide_no <= 0
                or type(self.shape_id) is not str or not self.shape_id
                or len(self.shape_id) > 256):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "SLIDE_SHAPE", "slide_no": self.slide_no,
                "shape_id": self.shape_id}


@dataclass(frozen=True, slots=True)
class SheetCellPosition:
    sheet_name: str
    cell: str

    def __post_init__(self) -> None:
        if (type(self.sheet_name) is not str or not self.sheet_name
                or len(self.sheet_name) > 128 or self.sheet_name != self.sheet_name.strip()
                or any(ord(char) < 32 for char in self.sheet_name)
                or type(self.cell) is not str or not self.cell):
            raise ParserResultError("PARSER_POSITION_INVALID")

    def to_locator(self) -> dict[str, object]:
        return {"locator_type": "SHEET_RANGE", "sheet_name": self.sheet_name,
                "start_cell": self.cell, "end_cell": self.cell}


@dataclass(frozen=True, slots=True)
class ParsedNode:
    node_id: str
    kind: str
    text: str = field(repr=False)
    position: (TextRangePosition | PdfTextRangePosition | PageBoxPosition
               | CsvCellPosition | ParagraphPosition
               | TableCellPosition | SlideShapePosition | SheetCellPosition)
    confidence: float | None = None

    def __post_init__(self) -> None:
        if (type(self.node_id) is not str or not self.node_id
                or len(self.node_id) > 256 or type(self.kind) is not str
                or self.kind not in ("TEXT_LINE", "PDF_TEXT_LINE", "OCR_LINE", "CSV_CELL", "DOCX_PARAGRAPH",
                                     "DOCX_TABLE_CELL", "PPTX_SHAPE", "PPTX_TABLE_CELL",
                                     "XLSX_CELL")
                or type(self.text) is not str
                or type(self.position) is not {
                    "TEXT_LINE": TextRangePosition,
                    "PDF_TEXT_LINE": PdfTextRangePosition,
                    "OCR_LINE": PageBoxPosition,
                    "CSV_CELL": CsvCellPosition,
                    "DOCX_PARAGRAPH": ParagraphPosition,
                    "DOCX_TABLE_CELL": TableCellPosition,
                    "PPTX_SHAPE": SlideShapePosition,
                    "PPTX_TABLE_CELL": TableCellPosition,
                    "XLSX_CELL": SheetCellPosition,
                }.get(self.kind)
                or (self.kind == "OCR_LINE") != (self.confidence is not None)
                or (self.confidence is not None
                    and (type(self.confidence) not in (int, float)
                         or not math.isfinite(self.confidence)
                         or not 0 <= self.confidence <= 1))):
            raise ParserResultError("PARSER_RESULT_INVALID")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"node_id": self.node_id, "kind": self.kind,
                                      "text": self.text,
                                      "source_locator": self.position.to_locator()}
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(frozen=True, slots=True)
class ParsedResult:
    document_version_id: uuid.UUID
    source_sha256: bytes = field(repr=False)
    parser_profile: str
    parser_version: str
    nodes: tuple[ParsedNode, ...] = field(repr=False)
    schema_version: str = _SCHEMA_VERSION
    ocr_model_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if (type(self.document_version_id) is not uuid.UUID
                or self.document_version_id.int == 0
                or type(self.source_sha256) is not bytes or len(self.source_sha256) != 32
                or type(self.parser_profile) is not str
                or self.parser_profile not in ("PLAIN_TEXT", "CSV", "DOCX", "PPTX", "XLSX",
                                               "PDF_TEXT_THEN_OCR", "IMAGE_OCR")
                or self.parser_version != "1" or self.schema_version != _SCHEMA_VERSION
                or type(self.nodes) is not tuple
                or any(type(node) is not ParsedNode for node in self.nodes)
                or any(node.kind not in {
                    "PLAIN_TEXT": ("TEXT_LINE",), "CSV": ("CSV_CELL",),
                    "PDF_TEXT_THEN_OCR": ("PDF_TEXT_LINE", "OCR_LINE"),
                    "IMAGE_OCR": ("OCR_LINE",),
                    "DOCX": ("DOCX_PARAGRAPH", "DOCX_TABLE_CELL"),
                    "PPTX": ("PPTX_SHAPE", "PPTX_TABLE_CELL"),
                    "XLSX": ("XLSX_CELL",),
                }[self.parser_profile] for node in self.nodes)
                or (any(node.kind == "OCR_LINE" for node in self.nodes)
                    != (self.ocr_model_fingerprint is not None))
                or (self.ocr_model_fingerprint is not None
                    and (type(self.ocr_model_fingerprint) is not str
                         or len(self.ocr_model_fingerprint) != 64
                         or any(char not in "0123456789abcdef"
                                for char in self.ocr_model_fingerprint)))
                or len({node.node_id for node in self.nodes}) != len(self.nodes)):
            raise ParserResultError("PARSER_RESULT_INVALID")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"schema_version": self.schema_version,
                "document_version_id": str(self.document_version_id),
                "source_sha256": self.source_sha256.hex(),
                "parser_profile": self.parser_profile,
                "parser_version": self.parser_version,
                "nodes": [node.to_payload() for node in self.nodes]}
        if self.ocr_model_fingerprint is not None:
            payload["ocr_model_fingerprint"] = self.ocr_model_fingerprint
        return payload

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")

    def result_sha256(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes()).digest()
