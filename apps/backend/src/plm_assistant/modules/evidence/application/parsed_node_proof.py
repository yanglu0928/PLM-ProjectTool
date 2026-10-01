"""Prove one Evidence locator against an authorized, fixed Parser node."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import (
    ParseResultReadError, VerifiedParseResult,
)
from plm_assistant.modules.evidence.domain.locator import (
    EvidenceLocatorError, validate_evidence_locator,
)


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
_PROFILE_VERSIONS = {profile: frozenset({"1", "2"}) if profile == "DOCX"
                     else frozenset({"1"}) for profile in _PROFILE_KINDS}


class EvidenceNodeProofError(RuntimeError):
    def __init__(self, code: str = "EVIDENCE_RESOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceParsedNodeProof:
    document_version_id: uuid.UUID
    parse_record_id: uuid.UUID
    node_id: str
    locator: dict[str, object]
    content_fingerprint: bytes = field(repr=False)
    precision: str = "PARSED_NODE"


class AuthorizedResultPort(Protocol):
    def read(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
             document_version_id: uuid.UUID,
             parse_record_id: uuid.UUID) -> VerifiedParseResult: ...


class ParsedNodeEvidenceProofService:
    def __init__(self, *, results: AuthorizedResultPort) -> None:
        if results is None:
            raise ValueError("authorized Document result Port required")
        self._results = results

    def prove(self, query: DocumentReadQuery, *, document_id: uuid.UUID,
              document_version_id: uuid.UUID, parse_record_id: uuid.UUID,
              locator: object) -> EvidenceParsedNodeProof:
        if (type(query) is not DocumentReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or query.scope not in ("GLOBAL", "PROJECT")
                or query.scope == "GLOBAL" and query.project_id is not None
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or query.project_id.int == 0)
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    document_id, document_version_id, parse_record_id))):
            raise EvidenceNodeProofError("VALIDATION_FAILED")
        try:
            canonical = validate_evidence_locator(locator)
        except EvidenceLocatorError:
            raise EvidenceNodeProofError("EVIDENCE_LOCATOR_INVALID") from None
        kind = canonical["locator_type"]
        if kind == "DOCUMENT":
            raise EvidenceNodeProofError()
        if kind == "STRUCTURED_NODE":
            if canonical["parse_record_id"] != str(parse_record_id):
                raise EvidenceNodeProofError("RESOURCE_NOT_FOUND")
            requested_source = canonical["source_locator"]
            requested_node = canonical["node_id"]
        else:
            requested_source = canonical
            requested_node = None
        try:
            result = self._results.read(
                query, document_id=document_id,
                document_version_id=document_version_id,
                parse_record_id=parse_record_id,
            )
        except ParseResultReadError as error:
            raise EvidenceNodeProofError(error.code) from None
        except Exception:
            raise EvidenceNodeProofError() from None
        if (type(result) is not VerifiedParseResult
                or result.parse_record_id != parse_record_id
                or result.document_version_id != document_version_id
                or type(result.content) is not bytes
                or type(result.source_sha256) is not bytes
                or len(result.source_sha256) != 32
                or type(result.result_sha256) is not bytes
                or len(result.result_sha256) != 32
                or not hmac.compare_digest(hashlib.sha256(result.content).digest(), result.result_sha256)):
            raise EvidenceNodeProofError()
        try:
            payload = json.loads(result.content, object_pairs_hook=_unique_object)
        except (ValueError, UnicodeDecodeError, TypeError):
            raise EvidenceNodeProofError() from None
        if (type(payload) is not dict or payload.get("schema_version") != "1"
                or payload.get("document_version_id") != str(document_version_id)
                or payload.get("source_sha256") != result.source_sha256.hex()
                or payload.get("parser_profile") != result.parser_profile
                or payload.get("parser_version") != result.parser_version
                or type(payload.get("nodes")) is not list
                or result.parser_profile not in _PROFILE_KINDS
                or result.parser_version not in _PROFILE_VERSIONS[result.parser_profile]):
            raise EvidenceNodeProofError()
        matched: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        for node in payload["nodes"]:
            if type(node) is not dict or not {"node_id", "kind", "text", "source_locator"}.issubset(node):
                raise EvidenceNodeProofError()
            node_id, node_kind, text = node["node_id"], node["kind"], node["text"]
            if (type(node_id) is not str or not node_id or len(node_id) > 256
                    or any(ord(char) < 32 for char in node_id)
                    or node_id in seen_ids or type(text) is not str
                    or type(node_kind) is not str
                    or node_kind not in _PROFILE_KINDS[result.parser_profile]):
                raise EvidenceNodeProofError()
            seen_ids.add(node_id)
            try:
                source = validate_evidence_locator(node["source_locator"])
            except EvidenceLocatorError:
                raise EvidenceNodeProofError() from None
            if source["locator_type"] != _KIND_LOCATOR[node_kind]:
                raise EvidenceNodeProofError()
            if node_kind == "DOCX_SECTION":
                parts = source["section_path"].split("/")
                if (result.parser_version != "2" or len(parts) != 4
                        or parts[:2] != ["word", "heading"]
                        or parts[2] not in tuple(str(level) for level in range(1, 10))
                        or not parts[3].isascii() or not parts[3].isdecimal()
                        or str(int(parts[3])) != parts[3] or int(parts[3]) <= 0
                        or node_id != f"heading:{parts[3]}"):
                    raise EvidenceNodeProofError()
            if text and source == requested_source and (requested_node is None or node_id == requested_node):
                matched.append((node_id, text))
        if len(matched) != 1:
            raise EvidenceNodeProofError()
        node_id, text = matched[0]
        try:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
        except UnicodeEncodeError:
            raise EvidenceNodeProofError() from None
        return EvidenceParsedNodeProof(
            document_version_id, parse_record_id, node_id, canonical, digest,
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Parser result field")
        result[key] = value
    return result
