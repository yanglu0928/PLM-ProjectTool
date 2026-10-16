"""Authorize and resolve Parser node ids to fixed DocumentVersion positions."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.document.domain.content_locator import (
    ContentLocatorError,
    validate_content_locator,
)

from .read_documents import (
    DocumentReadError,
    DocumentReadQuery,
    DocumentVersionView,
)
from .read_parse_result import ParseResultReadError, VerifiedParseResult


_KIND_LOCATOR = {
    "TEXT_LINE": "TEXT_RANGE",
    "PDF_TEXT_LINE": "TEXT_RANGE",
    "OCR_LINE": "PAGE",
    "CSV_CELL": "SHEET_RANGE",
    "DOCX_PARAGRAPH": "PARAGRAPH",
    "DOCX_SECTION": "SECTION",
    "DOCX_TABLE_CELL": "TABLE_CELL",
    "PPTX_SHAPE": "SLIDE_SHAPE",
    "PPTX_TABLE_CELL": "TABLE_CELL",
    "XLSX_CELL": "SHEET_RANGE",
}
_PROFILE_KINDS = {
    "PLAIN_TEXT": frozenset({"TEXT_LINE"}),
    "CSV": frozenset({"CSV_CELL"}),
    "DOCX": frozenset({"DOCX_PARAGRAPH", "DOCX_SECTION", "DOCX_TABLE_CELL"}),
    "PPTX": frozenset({"PPTX_SHAPE", "PPTX_TABLE_CELL"}),
    "XLSX": frozenset({"XLSX_CELL"}),
    "PDF_TEXT_THEN_OCR": frozenset({"PDF_TEXT_LINE", "OCR_LINE"}),
    "IMAGE_OCR": frozenset({"OCR_LINE"}),
}
_PROFILE_VERSIONS = {
    profile: frozenset({"1", "2"}) if profile == "DOCX" else frozenset({"1"})
    for profile in _PROFILE_KINDS
}
_MIME = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+\Z", re.ASCII)


class DocumentNodeLocationError(RuntimeError):
    def __init__(self, code: str = "DOCUMENT_NODE_LOCATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DocumentNodeLocation:
    node_id: str = field(repr=False)
    kind: str
    locator: dict[str, object] = field(repr=False)
    content_fingerprint: bytes = field(repr=False)
    precision: str
    display_label: str

    def __post_init__(self) -> None:
        try:
            canonical = validate_content_locator(self.locator)
        except ContentLocatorError:
            raise DocumentNodeLocationError() from None
        if (not _safe_node_id(self.node_id)
                or self.kind not in _KIND_LOCATOR
                or canonical != self.locator
                or canonical.get("locator_type") != "STRUCTURED_NODE"
                or canonical.get("node_id") != self.node_id
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or self.precision != "PARSED_NODE"
                or type(self.display_label) is not str
                or not 1 <= len(self.display_label) <= 255):
            raise DocumentNodeLocationError()


@dataclass(frozen=True, slots=True)
class DocumentNodeLocationSet:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    parse_record_id: uuid.UUID
    result_ref_id: uuid.UUID
    source_sha256: bytes = field(repr=False)
    result_sha256: bytes = field(repr=False)
    content_url: str
    locations: tuple[DocumentNodeLocation, ...]

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                    self.document_id, self.document_version_id, self.parse_record_id,
                    self.result_ref_id))
                or type(self.source_sha256) is not bytes
                or len(self.source_sha256) != 32
                or type(self.result_sha256) is not bytes
                or len(self.result_sha256) != 32
                or type(self.content_url) is not str
                or not self.content_url.startswith("/api/v1/")
                or type(self.locations) is not tuple or not self.locations
                or any(type(value) is not DocumentNodeLocation
                       for value in self.locations)):
            raise DocumentNodeLocationError()


@dataclass(frozen=True, slots=True)
class DocumentVersionLocation:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    source_sha256: bytes = field(repr=False)
    locator: dict[str, object]
    precision: str
    display_label: str
    content_url: str

    def __post_init__(self) -> None:
        try:
            canonical = validate_content_locator(self.locator)
        except ContentLocatorError:
            raise DocumentNodeLocationError() from None
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                    self.document_id, self.document_version_id))
                or canonical != {"locator_type": "DOCUMENT"}
                or type(self.source_sha256) is not bytes
                or len(self.source_sha256) != 32
                or canonical != self.locator or self.precision != "DOCUMENT"
                or self.display_label != "整个文档版本"
                or type(self.content_url) is not str
                or not self.content_url.startswith("/api/v1/")):
            raise DocumentNodeLocationError()


class AuthorizedParseResultPort(Protocol):
    def read(
        self, query: DocumentReadQuery, *, document_id: uuid.UUID,
        document_version_id: uuid.UUID, parse_record_id: uuid.UUID,
    ) -> VerifiedParseResult: ...


class AuthorizedVersionPort(Protocol):
    def get_version(
        self, query: DocumentReadQuery, document_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> DocumentVersionView: ...


class DocumentVersionLocationService:
    """Authorized DOCUMENT precision fallback for historical V1 suggestions."""

    def __init__(self, *, versions: AuthorizedVersionPort) -> None:
        if versions is None or not callable(getattr(versions, "get_version", None)):
            raise ValueError("authorized Document version Port required")
        self._versions = versions

    def resolve(
        self, query: DocumentReadQuery, *, document_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> DocumentVersionLocation:
        if (type(query) is not DocumentReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or query.scope not in ("GLOBAL", "PROJECT")
                or query.scope == "GLOBAL" and query.project_id is not None
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or not query.project_id.int)
                or any(type(value) is not uuid.UUID or not value.int for value in (
                    document_id, document_version_id))):
            raise DocumentNodeLocationError("VALIDATION_FAILED")
        try:
            version = self._versions.get_version(
                query, document_id, document_version_id,
            )
        except DocumentReadError as error:
            raise DocumentNodeLocationError(error.code) from None
        except Exception:
            raise DocumentNodeLocationError() from None
        if (type(version) is not DocumentVersionView
                or version.document_id != document_id
                or version.document_version_id != document_version_id
                or type(version.version_no) is not int or version.version_no <= 0
                or version.availability_state != "AVAILABLE"
                or type(version.content_sha256) is not str
                or len(version.content_sha256) != 64
                or any(char not in "0123456789abcdef"
                       for char in version.content_sha256)
                or type(version.size_bytes) is not int
                or not 0 <= version.size_bytes <= 100_000_000
                or type(version.detected_mime) is not str
                or _MIME.fullmatch(version.detected_mime) is None):
            raise DocumentNodeLocationError()
        return DocumentVersionLocation(
            document_id, document_version_id, bytes.fromhex(version.content_sha256),
            {"locator_type": "DOCUMENT"},
            "DOCUMENT", "整个文档版本",
            _content_url(query, document_id, document_version_id),
        )


class DocumentNodeLocationService:
    """Document Owner boundary; never trusts a model-provided locator."""

    def __init__(self, *, results: AuthorizedParseResultPort) -> None:
        if results is None or not callable(getattr(results, "read", None)):
            raise ValueError("authorized Document parse result Port required")
        self._results = results

    def resolve(
        self, query: DocumentReadQuery, *, document_id: uuid.UUID,
        document_version_id: uuid.UUID, parse_record_id: uuid.UUID,
        node_ids: tuple[str, ...],
    ) -> DocumentNodeLocationSet:
        if (type(query) is not DocumentReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or query.scope not in ("GLOBAL", "PROJECT")
                or query.scope == "GLOBAL" and query.project_id is not None
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or not query.project_id.int)
                or any(type(value) is not uuid.UUID or not value.int for value in (
                    document_id, document_version_id, parse_record_id))
                or type(node_ids) is not tuple or not 1 <= len(node_ids) <= 32
                or any(not _safe_node_id(value) for value in node_ids)
                or tuple(sorted(set(node_ids))) != node_ids):
            raise DocumentNodeLocationError("VALIDATION_FAILED")
        try:
            result = self._results.read(
                query, document_id=document_id,
                document_version_id=document_version_id,
                parse_record_id=parse_record_id,
            )
        except ParseResultReadError as error:
            raise DocumentNodeLocationError(error.code) from None
        except Exception:
            raise DocumentNodeLocationError() from None
        locations = _resolve_verified(
            result, document_version_id=document_version_id,
            parse_record_id=parse_record_id, node_ids=node_ids,
        )
        return DocumentNodeLocationSet(
            document_id, document_version_id, parse_record_id,
            result.result_ref_id, result.source_sha256, result.result_sha256,
            _content_url(query, document_id, document_version_id),
            locations,
        )


def _resolve_verified(
    result: VerifiedParseResult, *, document_version_id: uuid.UUID,
    parse_record_id: uuid.UUID, node_ids: tuple[str, ...],
) -> tuple[DocumentNodeLocation, ...]:
    if (type(result) is not VerifiedParseResult
            or result.document_version_id != document_version_id
            or result.parse_record_id != parse_record_id
            or type(result.content) is not bytes
            or type(result.source_sha256) is not bytes
            or len(result.source_sha256) != 32
            or type(result.result_sha256) is not bytes
            or len(result.result_sha256) != 32
            or not hmac.compare_digest(
                hashlib.sha256(result.content).digest(), result.result_sha256)):
        raise DocumentNodeLocationError()
    try:
        payload = json.loads(
            result.content, object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise DocumentNodeLocationError() from None
    expected_root = {
        "schema_version", "document_version_id", "source_sha256",
        "parser_profile", "parser_version", "nodes",
    }
    if type(payload) is dict and "ocr_model_fingerprint" in payload:
        expected_root.add("ocr_model_fingerprint")
    if (type(payload) is not dict or set(payload) != expected_root
            or canonical != result.content
            or payload.get("schema_version") != "1"
            or payload.get("document_version_id") != str(document_version_id)
            or payload.get("source_sha256") != result.source_sha256.hex()
            or payload.get("parser_profile") != result.parser_profile
            or payload.get("parser_version") != result.parser_version
            or result.parser_profile not in _PROFILE_KINDS
            or result.parser_version not in _PROFILE_VERSIONS[result.parser_profile]
            or type(payload.get("nodes")) is not list
            or not 1 <= len(payload["nodes"]) <= 1_000_000):
        raise DocumentNodeLocationError()

    requested = set(node_ids)
    found: dict[str, DocumentNodeLocation] = {}
    seen: set[str] = set()
    ocr_seen = False
    allowed_kinds = _PROFILE_KINDS[result.parser_profile]
    if result.parser_profile == "DOCX" and result.parser_version == "1":
        allowed_kinds = allowed_kinds - {"DOCX_SECTION"}
    for node in payload["nodes"]:
        if type(node) is not dict:
            raise DocumentNodeLocationError()
        expected_node = {"node_id", "kind", "text", "source_locator"}
        if "confidence" in node:
            expected_node.add("confidence")
        node_id, kind, text = node.get("node_id"), node.get("kind"), node.get("text")
        if (set(node) != expected_node or not _safe_node_id(node_id)
                or node_id in seen or type(kind) is not str
                or kind not in allowed_kinds or type(text) is not str):
            raise DocumentNodeLocationError()
        seen.add(node_id)
        has_confidence = "confidence" in node
        if has_confidence != (kind == "OCR_LINE"):
            raise DocumentNodeLocationError()
        if (has_confidence and (
                type(node["confidence"]) not in (int, float)
                or not math.isfinite(node["confidence"])
                or not 0 <= node["confidence"] <= 1)):
            raise DocumentNodeLocationError()
        ocr_seen = ocr_seen or kind == "OCR_LINE"
        try:
            source = validate_content_locator(node.get("source_locator"))
        except ContentLocatorError:
            raise DocumentNodeLocationError() from None
        if (source.get("locator_type") != _KIND_LOCATOR[kind]
                or source != node["source_locator"]):
            raise DocumentNodeLocationError()
        if kind == "DOCX_SECTION" and not _valid_docx_section(
                result.parser_version, node_id, source):
            raise DocumentNodeLocationError()
        if node_id in requested:
            if not text.strip():
                raise DocumentNodeLocationError()
            try:
                digest = hashlib.sha256(text.encode("utf-8")).digest()
                locator = validate_content_locator({
                    "locator_type": "STRUCTURED_NODE",
                    "parse_record_id": str(parse_record_id),
                    "node_id": node_id,
                    "source_locator": source,
                })
            except (ContentLocatorError, UnicodeError):
                raise DocumentNodeLocationError() from None
            found[node_id] = DocumentNodeLocation(
                node_id, kind, locator, digest, "PARSED_NODE", _display_label(source),
            )
    fingerprint = payload.get("ocr_model_fingerprint")
    if (ocr_seen != (fingerprint is not None)
            or fingerprint is not None and (
                type(fingerprint) is not str or len(fingerprint) != 64
                or any(char not in "0123456789abcdef" for char in fingerprint))
            or set(found) != requested):
        raise DocumentNodeLocationError()
    return tuple(found[node_id] for node_id in node_ids)


def _safe_node_id(value: object) -> bool:
    if (type(value) is not str or not value or len(value) > 256
            or value != value.strip()
            or unicodedata.normalize("NFC", value) != value):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return False
    return len(encoded) <= 512 and not any(
        unicodedata.category(char) in {"Cc", "Cs"} for char in value
    )


def _valid_docx_section(version: str, node_id: str,
                        source: dict[str, object]) -> bool:
    path = source.get("section_path")
    if type(path) is not str:
        return False
    parts = path.split("/")
    return (version == "2" and len(parts) == 4
            and parts[:2] == ["word", "heading"]
            and parts[2] in tuple(str(level) for level in range(1, 10))
            and parts[3].isascii() and parts[3].isdecimal()
            and str(int(parts[3])) == parts[3] and int(parts[3]) > 0
            and node_id == f"heading:{parts[3]}")


def _display_label(locator: dict[str, object]) -> str:
    kind = locator["locator_type"]
    if kind == "PAGE":
        value = f"第 {locator['page_no']} 页"
    elif kind == "TEXT_RANGE":
        prefix = (f"第 {locator['page_no']} 页" if "page_no" in locator
                  else "文本文档")
        value = f"{prefix} / 字符 {locator['start_offset']}–{locator['end_offset']}"
    elif kind == "SECTION":
        value = f"章节 {locator['section_path']}"
    elif kind == "PARAGRAPH":
        position = locator.get("paragraph_index", locator.get("stable_anchor"))
        value = f"段落 {position}"
        if "page_no" in locator:
            value = f"第 {locator['page_no']} 页 / {value}"
    elif kind == "TABLE_CELL":
        value = (f"表格 {locator['table_anchor']} / 行 {locator['row_no']}"
                 f" / 列 {locator['column_no']}")
    elif kind == "SHEET_RANGE":
        value = (f"{locator['sheet_name']}!{locator['start_cell']}"
                 f":{locator['end_cell']}")
    elif kind == "SLIDE_SHAPE":
        value = f"第 {locator['slide_no']} 张幻灯片 / 图形 {locator['shape_id']}"
    else:
        raise DocumentNodeLocationError()
    return value if len(value) <= 255 else value[:254] + "…"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Parser result field")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError("non-finite Parser result number")


def _content_url(query: DocumentReadQuery, document_id: uuid.UUID,
                 document_version_id: uuid.UUID) -> str:
    base = (f"/api/v1/projects/{query.project_id}"
            if query.scope == "PROJECT" else "/api/v1/global")
    return (f"{base}/documents/{document_id}/versions/"
            f"{document_version_id}/content")
