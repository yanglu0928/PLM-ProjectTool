"""Trusted, versioned validators for Provider-produced suggestion payloads."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field as dataclass_field
from typing import Protocol


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z")
_CATEGORIES = frozenset({
    "STANDARD_FUNCTION",
    "NONSTANDARD_FUNCTION",
    "DIFFERENCE",
    "PENDING_CONFIRMATION",
})


class AIOutputSchemaError(RuntimeError):
    def __init__(self, code: str = "AI_OUTPUT_SCHEMA_INVALID") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidatedAIOutput:
    canonical_json: bytes
    evidence_ordinals: tuple[int, ...]
    source_citations: tuple["ValidatedAISourceCitation", ...] = ()

    def __post_init__(self) -> None:
        if (type(self.canonical_json) is not bytes
                or not 2 <= len(self.canonical_json) <= 1_048_576
                or type(self.evidence_ordinals) is not tuple
                or not self.evidence_ordinals
                or any(type(value) is not int or not 1 <= value <= 1000
                       for value in self.evidence_ordinals)
                or tuple(sorted(set(self.evidence_ordinals)))
                != self.evidence_ordinals
                or type(self.source_citations) is not tuple
                or any(type(value) is not ValidatedAISourceCitation
                       for value in self.source_citations)
                or self.source_citations and tuple(
                    value.source_ordinal for value in self.source_citations
                ) != self.evidence_ordinals):
            raise AIOutputSchemaError()


@dataclass(frozen=True, slots=True)
class ValidatedAISourceCitation:
    source_ordinal: int
    node_ids: tuple[str, ...] = dataclass_field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.source_ordinal) is not int
                or not 1 <= self.source_ordinal <= 1000
                or type(self.node_ids) is not tuple or not self.node_ids
                or len(self.node_ids) > 32
                or any(not _text(value, maximum_bytes=512)
                       for value in self.node_ids)
                or tuple(sorted(set(self.node_ids))) != self.node_ids):
            raise AIOutputSchemaError()


class AIOutputSchemaPort(Protocol):
    schema_ref: str
    schema_version: int

    def validate(
        self, payload: object, *, allowed_source_ordinals: frozenset[int],
        allowed_source_nodes: Mapping[int, frozenset[str]] | None = None,
    ) -> ValidatedAIOutput: ...


def _text(value: object, *, maximum_bytes: int) -> bool:
    if (type(value) is not str or not value
            or value != value.strip()
            or unicodedata.normalize("NFC", value) != value
            or any(ord(char) < 32 and char not in "\n\t" for char in value)
            or any(0xD800 <= ord(char) <= 0xDFFF for char in value)):
        return False
    try:
        return len(value.encode("utf-8")) <= maximum_bytes
    except UnicodeError:
        return False


@dataclass(frozen=True, slots=True)
class GapOutputSchemaV1:
    schema_ref: str = "gap-output.v1"
    schema_version: int = 1
    _ROOT_FIELDS = frozenset({"schema_ref", "schema_version", "items"})
    _ITEM_FIELDS = frozenset({
        "category", "title", "summary", "rationale", "recommendation",
        "source_ordinals",
    })

    def validate(
        self, payload: object, *, allowed_source_ordinals: frozenset[int],
        allowed_source_nodes: Mapping[int, frozenset[str]] | None = None,
    ) -> ValidatedAIOutput:
        if (type(payload) is not dict or set(payload) != self._ROOT_FIELDS
                or payload.get("schema_ref") != self.schema_ref
                or type(payload.get("schema_version")) is not int
                or payload.get("schema_version") != self.schema_version
                or type(payload.get("items")) is not list
                or not 1 <= len(payload["items"]) <= 100
                or type(allowed_source_ordinals) is not frozenset
                or not allowed_source_ordinals):
            raise AIOutputSchemaError()
        evidence: set[int] = set()
        for item in payload["items"]:
            if (type(item) is not dict or set(item) != self._ITEM_FIELDS
                    or type(item.get("category")) is not str
                    or item.get("category") not in _CATEGORIES
                    or not _text(item.get("title"), maximum_bytes=512)
                    or not _text(item.get("summary"), maximum_bytes=8192)
                    or not _text(item.get("rationale"), maximum_bytes=8192)
                    or not _text(item.get("recommendation"), maximum_bytes=8192)):
                raise AIOutputSchemaError()
            ordinals = item.get("source_ordinals")
            if (type(ordinals) is not list or not 1 <= len(ordinals) <= 32
                    or any(type(value) is not int or value not in allowed_source_ordinals
                           for value in ordinals)
                    or ordinals != sorted(set(ordinals))):
                raise AIOutputSchemaError()
            evidence.update(ordinals)
        try:
            canonical = json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise AIOutputSchemaError() from None
        if len(canonical) > 1_048_576:
            raise AIOutputSchemaError()
        return ValidatedAIOutput(canonical, tuple(sorted(evidence)))


_CONFIRMATION_FIELD_KEYS = frozenset({
    "ACTUAL_STATE", "DECISION", "OWNER", "TARGET_DATE", "SCOPE",
    "CONSTRAINT", "EXCEPTION", "NOTES",
})


@dataclass(frozen=True, slots=True)
class GapOutputSchemaV2:
    schema_ref: str = "gap-output.v2"
    schema_version: int = 2
    _ROOT_FIELDS = frozenset({"schema_ref", "schema_version", "items"})
    _ITEM_FIELDS = frozenset({
        "category", "title", "summary", "rationale", "recommendation",
        "source_citations", "confirmation",
    })
    _CITATION_FIELDS = frozenset({"source_ordinal", "node_ids"})
    _CONFIRMATION_FIELDS = frozenset({"required", "question", "required_fields"})
    _REQUIRED_FIELD_FIELDS = frozenset({
        "key", "label", "prompt", "reason", "required",
    })

    def validate(
        self, payload: object, *, allowed_source_ordinals: frozenset[int],
        allowed_source_nodes: Mapping[int, frozenset[str]] | None = None,
    ) -> ValidatedAIOutput:
        if (type(payload) is not dict or set(payload) != self._ROOT_FIELDS
                or payload.get("schema_ref") != self.schema_ref
                or payload.get("schema_version") != self.schema_version
                or type(payload.get("schema_version")) is not int
                or type(payload.get("items")) is not list
                or not 1 <= len(payload["items"]) <= 100
                or type(allowed_source_ordinals) is not frozenset
                or not allowed_source_ordinals
                or not isinstance(allowed_source_nodes, Mapping)
                or set(allowed_source_nodes) != set(allowed_source_ordinals)
                or any(type(nodes) is not frozenset or not nodes
                       for nodes in allowed_source_nodes.values())):
            raise AIOutputSchemaError()
        citation_nodes: dict[int, set[str]] = {}
        for item in payload["items"]:
            self._validate_item(
                item, allowed_source_ordinals=allowed_source_ordinals,
                allowed_source_nodes=allowed_source_nodes,
                citation_nodes=citation_nodes,
            )
        try:
            canonical = json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise AIOutputSchemaError() from None
        if len(canonical) > 1_048_576:
            raise AIOutputSchemaError()
        citations = tuple(
            ValidatedAISourceCitation(ordinal, tuple(sorted(nodes)))
            for ordinal, nodes in sorted(citation_nodes.items())
        )
        return ValidatedAIOutput(
            canonical, tuple(value.source_ordinal for value in citations), citations,
        )

    def _validate_item(
        self, item: object, *, allowed_source_ordinals: frozenset[int],
        allowed_source_nodes: Mapping[int, frozenset[str]],
        citation_nodes: dict[int, set[str]],
    ) -> None:
        if (type(item) is not dict or set(item) != self._ITEM_FIELDS
                or type(item.get("category")) is not str
                or item.get("category") not in _CATEGORIES
                or not _text(item.get("title"), maximum_bytes=512)
                or not _text(item.get("summary"), maximum_bytes=8192)
                or not _text(item.get("rationale"), maximum_bytes=8192)
                or not _text(item.get("recommendation"), maximum_bytes=8192)):
            raise AIOutputSchemaError()
        citations = item.get("source_citations")
        if type(citations) is not list or not 1 <= len(citations) <= 32:
            raise AIOutputSchemaError()
        seen: list[int] = []
        for citation in citations:
            if type(citation) is not dict or set(citation) != self._CITATION_FIELDS:
                raise AIOutputSchemaError()
            ordinal = citation.get("source_ordinal")
            nodes = citation.get("node_ids")
            allowed = allowed_source_nodes.get(ordinal) if type(ordinal) is int else None
            if (type(ordinal) is not int or ordinal not in allowed_source_ordinals
                    or type(nodes) is not list or not 1 <= len(nodes) <= 32
                    or any(not _text(value, maximum_bytes=512) for value in nodes)
                    or nodes != sorted(set(nodes))
                    or type(allowed) is not frozenset
                    or any(value not in allowed for value in nodes)):
                raise AIOutputSchemaError()
            seen.append(ordinal)
            citation_nodes.setdefault(ordinal, set()).update(nodes)
        if seen != sorted(set(seen)):
            raise AIOutputSchemaError()
        self._validate_confirmation(item["category"], item.get("confirmation"))

    def _validate_confirmation(self, category: str, value: object) -> None:
        if type(value) is not dict or set(value) != self._CONFIRMATION_FIELDS:
            raise AIOutputSchemaError()
        required = value.get("required")
        expected = category == "PENDING_CONFIRMATION"
        fields = value.get("required_fields")
        question = value.get("question")
        if (type(required) is not bool or required != expected
                or type(fields) is not list
                or (required and not 1 <= len(fields) <= 8)
                or (not required and fields)
                or (required and not _text(question, maximum_bytes=2048))
                or (not required and question is not None)):
            raise AIOutputSchemaError()
        seen: set[str] = set()
        required_count = 0
        for field_value in fields:
            if (type(field_value) is not dict
                    or set(field_value) != self._REQUIRED_FIELD_FIELDS
                    or field_value.get("key") not in _CONFIRMATION_FIELD_KEYS
                    or field_value["key"] in seen
                    or not _text(field_value.get("label"), maximum_bytes=256)
                    or not _text(field_value.get("prompt"), maximum_bytes=2048)
                    or not _text(field_value.get("reason"), maximum_bytes=2048)
                    or type(field_value.get("required")) is not bool):
                raise AIOutputSchemaError()
            seen.add(field_value["key"])
            required_count += int(field_value["required"])
        if required and required_count == 0:
            raise AIOutputSchemaError()


class AIOutputSchemaRegistry:
    def __init__(self, schemas: tuple[AIOutputSchemaPort, ...]) -> None:
        if type(schemas) is not tuple or not schemas:
            raise ValueError("AI output schemas required")
        values: dict[tuple[str, int], AIOutputSchemaPort] = {}
        for schema in schemas:
            ref = getattr(schema, "schema_ref", None)
            version = getattr(schema, "schema_version", None)
            if (type(ref) is not str or _REF.fullmatch(ref) is None
                    or type(version) is not int or version < 1
                    or not callable(getattr(schema, "validate", None))
                    or (ref, version) in values):
                raise ValueError("invalid AI output schema registry")
            values[(ref, version)] = schema
        self._schemas = values

    def resolve(self, schema_ref: str, schema_version: int) -> AIOutputSchemaPort:
        if (type(schema_ref) is not str or _REF.fullmatch(schema_ref) is None
                or type(schema_version) is not int or schema_version < 1):
            raise AIOutputSchemaError("AI_OUTPUT_SCHEMA_UNKNOWN")
        schema = self._schemas.get((schema_ref, schema_version))
        if schema is None:
            raise AIOutputSchemaError("AI_OUTPUT_SCHEMA_UNKNOWN")
        return schema


def default_ai_output_schema_registry() -> AIOutputSchemaRegistry:
    return AIOutputSchemaRegistry((
        GapOutputSchemaV1("gap-output.v1", 1),
        GapOutputSchemaV1("gap-analysis-output.v1", 1),
        GapOutputSchemaV2("gap-output.v2", 2),
        GapOutputSchemaV2("gap-analysis-output.v2", 2),
    ))
