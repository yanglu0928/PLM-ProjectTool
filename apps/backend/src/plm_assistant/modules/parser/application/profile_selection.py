"""Bind a parse strategy to one immutable version's verified metadata.

The caller must obtain this descriptor through an authorized Document snapshot;
constructing it does not authorize content access or prove file integrity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


_MAX_SOURCE_BYTES = 100_000_000
_PROFILE_VERSION = "1"
_PROFILES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "application/pdf": ("PDF_TEXT_THEN_OCR", "TEXT_FIRST_OCR_IF_NEEDED",
                        ("PyMuPDF", "pdfplumber", "PaddleOCR", "Tesseract", "OCRmyPDF")),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "DOCX", "NONE", ("python-docx",)),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "PPTX", "NONE", ("python-pptx",)),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "XLSX", "NONE", ("openpyxl",)),
    "text/csv": ("CSV", "NONE", ("python-csv",)),
    "text/plain": ("PLAIN_TEXT", "NONE", ("python-text",)),
    "image/png": ("IMAGE_OCR", "REQUIRED", ("PaddleOCR", "Tesseract")),
    "image/jpeg": ("IMAGE_OCR", "REQUIRED", ("PaddleOCR", "Tesseract")),
    "image/tiff": ("IMAGE_OCR", "REQUIRED", ("PaddleOCR", "Tesseract")),
}


class ParserProfileError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParserInputVersion:
    document_version_id: uuid.UUID
    content_sha256: bytes = field(repr=False)
    size_bytes: int
    detected_mime: str

    def validate(self) -> None:
        if (type(self.document_version_id) is not uuid.UUID
                or self.document_version_id.int == 0
                or type(self.content_sha256) is not bytes
                or len(self.content_sha256) != 32
                or type(self.size_bytes) is not int
                or not 0 <= self.size_bytes <= _MAX_SOURCE_BYTES
                or type(self.detected_mime) is not str
                or not self.detected_mime
                or self.detected_mime != self.detected_mime.strip()
                or len(self.detected_mime) > 255):
            raise ParserProfileError("PARSER_INPUT_INVALID")

    def __post_init__(self) -> None:
        self.validate()


@dataclass(frozen=True, slots=True)
class ParserProfilePlan:
    source: ParserInputVersion
    parser_profile: str
    parser_version: str
    ocr_policy: str
    component_order: tuple[str, ...]


def choose_parser_profile(source: ParserInputVersion) -> ParserProfilePlan:
    """Choose a versioned plan; no parsing, OCR, authorization or Job mutation."""
    if type(source) is not ParserInputVersion:
        raise ParserProfileError("PARSER_INPUT_INVALID")
    source.validate()
    choice = _PROFILES.get(source.detected_mime)
    if choice is None:
        raise ParserProfileError("PARSER_FORMAT_UNSUPPORTED")
    profile, policy, components = choice
    return ParserProfilePlan(source, profile, _PROFILE_VERSION, policy, components)
