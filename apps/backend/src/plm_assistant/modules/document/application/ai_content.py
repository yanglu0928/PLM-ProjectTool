"""Document-owned exact parsed-text projection for AI execution.

This boundary never returns a storage locator to AI.  Planning selects one
successful ParseRecord deterministically; execution can only reread that exact
immutable ParseRecord/ParseResultRef after current authority is rechecked.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)


_PARSER_VERSIONS = frozenset({
    ("PLAIN_TEXT", "1"), ("CSV", "1"), ("DOCX", "1"), ("DOCX", "2"),
    ("PPTX", "1"), ("XLSX", "1"), ("PDF_TEXT_THEN_OCR", "1"),
    ("IMAGE_OCR", "1"),
})
_NODE_KINDS = {
    "PLAIN_TEXT": frozenset({"TEXT_LINE"}),
    "CSV": frozenset({"CSV_CELL"}),
    "DOCX": frozenset({"DOCX_PARAGRAPH", "DOCX_SECTION", "DOCX_TABLE_CELL"}),
    "PPTX": frozenset({"PPTX_SHAPE", "PPTX_TABLE_CELL"}),
    "XLSX": frozenset({"XLSX_CELL"}),
    "PDF_TEXT_THEN_OCR": frozenset({"PDF_TEXT_LINE", "OCR_LINE"}),
    "IMAGE_OCR": frozenset({"OCR_LINE"}),
}
_BIDI_CONTROLS = frozenset({
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c",
    "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069",
})


class DocumentAIContentError(RuntimeError):
    def __init__(self, code: str = "DOCUMENT_AI_CONTENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


@dataclass(frozen=True, slots=True)
class DocumentAIContentPolicy:
    selection_policy_ref: str = "document.parse.fixed.v1"
    minimal_payload_policy_ref: str = "minimum.document.text.v1"
    projection_schema_ref: str = "document.minimum-text.v1"
    allowed_parser_versions: frozenset[tuple[str, str]] = _PARSER_VERSIONS
    max_result_bytes: int = 100_000_000
    max_records: int = 1_000_000
    max_projection_bytes: int = 100_000_000

    def __post_init__(self) -> None:
        if (self.selection_policy_ref != "document.parse.fixed.v1"
                or self.minimal_payload_policy_ref != "minimum.document.text.v1"
                or self.projection_schema_ref != "document.minimum-text.v1"
                or type(self.allowed_parser_versions) is not frozenset
                or not self.allowed_parser_versions
                or not self.allowed_parser_versions <= _PARSER_VERSIONS
                or type(self.max_result_bytes) is not int
                or not 1 <= self.max_result_bytes <= 100_000_000
                or type(self.max_records) is not int
                or not 1 <= self.max_records <= 1_000_000
                or type(self.max_projection_bytes) is not int
                or not 1 <= self.max_projection_bytes <= 100_000_000):
            raise DocumentAIContentError("DOCUMENT_AI_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class DocumentAIContentQuery:
    project_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    purpose_ref: str
    minimal_payload_policy_ref: str
    selection_policy_ref: str

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.project_id, self.actor_id, self.trace_id,
                ))
                or type(self.purpose_ref) is not str or not self.purpose_ref
                or len(self.purpose_ref) > 128
                or type(self.minimal_payload_policy_ref) is not str
                or type(self.selection_policy_ref) is not str):
            raise DocumentAIContentError()


@dataclass(frozen=True, slots=True)
class DocumentAIContentSource:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    project_id: uuid.UUID
    parse_record_id: uuid.UUID
    result_ref_id: uuid.UUID
    parser_profile: str
    parser_version: str
    storage_locator: str = field(repr=False)
    source_sha256: bytes = field(repr=False)
    result_sha256: bytes = field(repr=False)
    result_size_bytes: int
    result_schema_version: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.document_id, self.document_version_id, self.project_id,
                    self.parse_record_id, self.result_ref_id,
                ))
                or type(self.parser_profile) is not str
                or type(self.parser_version) is not str
                or type(self.storage_locator) is not str or not self.storage_locator
                or not _digest(self.source_sha256)
                or not _digest(self.result_sha256)
                or type(self.result_size_bytes) is not int
                or not 1 <= self.result_size_bytes <= 100_000_000
                or self.result_schema_version != 1):
            raise DocumentAIContentError()


@dataclass(frozen=True, slots=True)
class DocumentAIContentIdentity:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    project_id: uuid.UUID
    parse_record_id: uuid.UUID
    result_ref_id: uuid.UUID
    parser_profile: str
    parser_version: str
    selection_policy_ref: str
    source_sha256: bytes = field(repr=False)
    result_sha256: bytes = field(repr=False)
    projection_sha256: bytes = field(repr=False)
    result_size_bytes: int
    record_count: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.document_id, self.document_version_id, self.project_id,
                    self.parse_record_id, self.result_ref_id,
                ))
                or (self.parser_profile, self.parser_version) not in _PARSER_VERSIONS
                or self.selection_policy_ref != "document.parse.fixed.v1"
                or not _digest(self.source_sha256)
                or not _digest(self.result_sha256)
                or not _digest(self.projection_sha256)
                or type(self.result_size_bytes) is not int
                or not 1 <= self.result_size_bytes <= 100_000_000
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 1_000_000):
            raise DocumentAIContentError()


@dataclass(frozen=True, slots=True)
class DocumentAIContentProjection:
    identity: DocumentAIContentIdentity
    projection_schema_ref: str
    content_utf8: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.identity) is not DocumentAIContentIdentity
                or self.projection_schema_ref != "document.minimum-text.v1"
                or type(self.content_utf8) is not bytes
                or not 1 <= len(self.content_utf8) <= 100_000_000):
            raise DocumentAIContentError()
        try:
            decoded = self.content_utf8.decode("utf-8")
        except UnicodeDecodeError:
            raise DocumentAIContentError() from None
        if not decoded.strip():
            raise DocumentAIContentError()

    @property
    def projection_fingerprint(self) -> bytes:
        return hashlib.sha256(self.content_utf8).digest()


class DocumentAIContentRepositoryPort(Protocol):
    def select_current(
        self, transaction: object, *, project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
        allowed_parser_versions: frozenset[tuple[str, str]],
        max_result_bytes: int,
    ) -> DocumentAIContentSource | None: ...

    def get_exact(
        self, transaction: object, *, project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
        parse_record_id: uuid.UUID, result_ref_id: uuid.UUID,
    ) -> DocumentAIContentSource | None: ...


class DocumentAIContentStoragePort(Protocol):
    def read_verified(
        self, *, scope: str, project_id: uuid.UUID | None,
        result_ref_id: uuid.UUID, expected_locator: str,
        expected_sha256: bytes, expected_size: int,
    ) -> bytes: ...


class DocumentAILicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class DocumentAIContentService:
    def __init__(
        self, *, repository: DocumentAIContentRepositoryPort,
        storage: DocumentAIContentStoragePort,
        projects: ProjectAuthorizationService,
        license_guard: DocumentAILicenseGuardPort,
        policy: DocumentAIContentPolicy | None = None,
    ) -> None:
        if any(value is None for value in (
                repository, storage, projects, license_guard)):
            raise ValueError("Document AI content dependencies required")
        self._repository = repository
        self._storage = storage
        self._projects = projects
        self._guard = license_guard
        self._policy = policy or DocumentAIContentPolicy()

    def resolve_identity(
        self, transaction: object, *, query: DocumentAIContentQuery,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
    ) -> DocumentAIContentIdentity:
        self._validate_request(query, document_id, document_version_id)
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            self._authorize(transaction, query)
            source = self._repository.select_current(
                transaction, project_id=query.project_id,
                document_id=document_id, document_version_id=document_version_id,
                allowed_parser_versions=self._policy.allowed_parser_versions,
                max_result_bytes=self._policy.max_result_bytes,
            )
            source = self._require_source(
                source, query.project_id, document_id, document_version_id)
            projection, count = self._read_and_project(source)
            current = self._repository.get_exact(
                transaction, project_id=query.project_id,
                document_id=document_id, document_version_id=document_version_id,
                parse_record_id=source.parse_record_id,
                result_ref_id=source.result_ref_id,
            )
            if current != source:
                raise DocumentAIContentError()
            self._guard.require_valid(trace_id=query.trace_id)
            return self._identity(source, count, projection)
        except DocumentAIContentError:
            raise
        except Exception:
            raise DocumentAIContentError() from None

    def read_exact(
        self, transaction: object, *, query: DocumentAIContentQuery,
        identity: DocumentAIContentIdentity,
    ) -> DocumentAIContentProjection:
        if type(identity) is not DocumentAIContentIdentity:
            raise DocumentAIContentError()
        identity.__post_init__()
        self._validate_request(
            query, identity.document_id, identity.document_version_id)
        if (identity.project_id != query.project_id
                or identity.selection_policy_ref
                != self._policy.selection_policy_ref):
            raise DocumentAIContentError()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            self._authorize(transaction, query)
            source = self._repository.get_exact(
                transaction, project_id=query.project_id,
                document_id=identity.document_id,
                document_version_id=identity.document_version_id,
                parse_record_id=identity.parse_record_id,
                result_ref_id=identity.result_ref_id,
            )
            source = self._require_source(
                source, query.project_id, identity.document_id,
                identity.document_version_id)
            if not self._source_matches_identity(source, identity):
                raise DocumentAIContentError()
            projection, count = self._read_and_project(source)
            if (count != identity.record_count
                    or not hmac.compare_digest(
                        hashlib.sha256(projection).digest(),
                        identity.projection_sha256)):
                raise DocumentAIContentError()
            current = self._repository.get_exact(
                transaction, project_id=query.project_id,
                document_id=identity.document_id,
                document_version_id=identity.document_version_id,
                parse_record_id=identity.parse_record_id,
                result_ref_id=identity.result_ref_id,
            )
            if current != source:
                raise DocumentAIContentError()
            self._guard.require_valid(trace_id=query.trace_id)
            return DocumentAIContentProjection(
                identity, self._policy.projection_schema_ref, projection)
        except DocumentAIContentError:
            raise
        except Exception:
            raise DocumentAIContentError() from None

    def _validate_request(
        self, query: DocumentAIContentQuery,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
    ) -> None:
        if type(query) is not DocumentAIContentQuery:
            raise DocumentAIContentError()
        query.__post_init__()
        if (not _id(document_id) or not _id(document_version_id)
                or query.selection_policy_ref != self._policy.selection_policy_ref
                or query.minimal_payload_policy_ref
                != self._policy.minimal_payload_policy_ref):
            raise DocumentAIContentError()

    def _authorize(self, transaction: object, query: DocumentAIContentQuery) -> None:
        self._projects.require_in_transaction(
            transaction, user_id=query.actor_id, project_id=query.project_id,
            operation="AI_TASK_EXECUTE",
        )

    def _require_source(
        self, source: object, project_id: uuid.UUID,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
    ) -> DocumentAIContentSource:
        if type(source) is not DocumentAIContentSource:
            raise DocumentAIContentError()
        source.__post_init__()
        if (source.project_id != project_id or source.document_id != document_id
                or source.document_version_id != document_version_id
                or (source.parser_profile, source.parser_version)
                not in self._policy.allowed_parser_versions
                or source.result_size_bytes > self._policy.max_result_bytes):
            raise DocumentAIContentError()
        return source

    def _read_and_project(self, source: DocumentAIContentSource) -> tuple[bytes, int]:
        try:
            content = self._storage.read_verified(
                scope="PROJECT", project_id=source.project_id,
                result_ref_id=source.result_ref_id,
                expected_locator=source.storage_locator,
                expected_sha256=source.result_sha256,
                expected_size=source.result_size_bytes,
            )
        except Exception:
            raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INTEGRITY_MISMATCH") from None
        if (type(content) is not bytes or len(content) != source.result_size_bytes
                or not hmac.compare_digest(
                    hashlib.sha256(content).digest(), source.result_sha256)):
            raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INTEGRITY_MISMATCH")
        return _minimum_text_projection(content, source, self._policy)

    def _identity(
        self, source: DocumentAIContentSource, record_count: int,
        projection: bytes,
    ) -> DocumentAIContentIdentity:
        return DocumentAIContentIdentity(
            source.document_id, source.document_version_id, source.project_id,
            source.parse_record_id, source.result_ref_id,
            source.parser_profile, source.parser_version,
            self._policy.selection_policy_ref, source.source_sha256,
            source.result_sha256, hashlib.sha256(projection).digest(),
            source.result_size_bytes, record_count,
        )

    @staticmethod
    def _source_matches_identity(
        source: DocumentAIContentSource,
        identity: DocumentAIContentIdentity,
    ) -> bool:
        return (source.document_id == identity.document_id
                and source.document_version_id == identity.document_version_id
                and source.project_id == identity.project_id
                and source.parse_record_id == identity.parse_record_id
                and source.result_ref_id == identity.result_ref_id
                and source.parser_profile == identity.parser_profile
                and source.parser_version == identity.parser_version
                and hmac.compare_digest(
                    source.source_sha256, identity.source_sha256)
                and hmac.compare_digest(
                    source.result_sha256, identity.result_sha256)
                and source.result_size_bytes == identity.result_size_bytes)


def _minimum_text_projection(
    content: bytes, source: DocumentAIContentSource,
    policy: DocumentAIContentPolicy,
) -> tuple[bytes, int]:
    try:
        text = content.decode("utf-8")
        payload = json.loads(
            text, object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError):
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID") from None
    if type(payload) is not dict:
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
    expected_keys = {
        "schema_version", "document_version_id", "source_sha256",
        "parser_profile", "parser_version", "nodes",
    }
    if "ocr_model_fingerprint" in payload:
        expected_keys.add("ocr_model_fingerprint")
    if (set(payload) != expected_keys
            or payload.get("schema_version") != "1"
            or payload.get("document_version_id") != str(source.document_version_id)
            or payload.get("source_sha256") != source.source_sha256.hex()
            or payload.get("parser_profile") != source.parser_profile
            or payload.get("parser_version") != source.parser_version
            or type(payload.get("nodes")) is not list):
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
    # Parser publication is canonical.  Refuse alternate JSON spellings or
    # duplicate-key ambiguity even when their decoded values look equivalent.
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    if canonical != content:
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
    nodes = payload["nodes"]
    if not 1 <= len(nodes) <= policy.max_records:
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_LIMIT_EXCEEDED")
    allowed_kinds = _NODE_KINDS[source.parser_profile]
    if source.parser_profile == "DOCX" and source.parser_version == "1":
        allowed_kinds = allowed_kinds - {"DOCX_SECTION"}
    projected: list[dict[str, str]] = []
    seen: set[str] = set()
    ocr_seen = False
    for node in nodes:
        if type(node) is not dict:
            raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
        expected_node_keys = {"node_id", "kind", "text", "source_locator"}
        if "confidence" in node:
            expected_node_keys.add("confidence")
        node_id, kind, node_text = (
            node.get("node_id"), node.get("kind"), node.get("text"))
        if (set(node) != expected_node_keys
                or type(node_id) is not str or not 1 <= len(node_id) <= 256
                or node_id in seen or type(kind) is not str
                or kind not in allowed_kinds or type(node_text) is not str
                or type(node.get("source_locator")) is not dict
                or not node["source_locator"]):
            raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
        seen.add(node_id)
        has_confidence = "confidence" in node
        if kind == "OCR_LINE":
            ocr_seen = True
        if has_confidence != (kind == "OCR_LINE"):
            raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
        if has_confidence and (type(node["confidence"]) not in (int, float)
                               or not math.isfinite(node["confidence"])
                               or not 0 <= node["confidence"] <= 1):
            raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
        normalized = _safe_text(node_text)
        if normalized.strip():
            projected.append({
                "node_id": node_id, "kind": kind, "text": normalized,
            })
    fingerprint = payload.get("ocr_model_fingerprint")
    if (ocr_seen != (fingerprint is not None)
            or (fingerprint is not None
                and (type(fingerprint) is not str or len(fingerprint) != 64
                     or any(char not in "0123456789abcdef" for char in fingerprint)))):
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
    if not projected:
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_EMPTY")
    result = json.dumps({
        "nodes": projected, "schema_version": "document-minimum-text-v1",
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(result) > policy.max_projection_bytes:
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_LIMIT_EXCEEDED")
    return result, len(projected)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> object:
    raise ValueError("non-finite JSON number")


def _safe_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    if any((unicodedata.category(char) in {"Cc", "Cs"}
            and char not in {"\n", "\t"}) or char in _BIDI_CONTROLS
           for char in normalized):
        raise DocumentAIContentError("DOCUMENT_AI_CONTENT_INVALID")
    return normalized
