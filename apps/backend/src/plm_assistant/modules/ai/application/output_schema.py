"""Trusted, versioned validators for Provider-produced suggestion payloads."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
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

    def __post_init__(self) -> None:
        if (type(self.canonical_json) is not bytes
                or not 2 <= len(self.canonical_json) <= 1_048_576
                or type(self.evidence_ordinals) is not tuple
                or not self.evidence_ordinals
                or any(type(value) is not int or not 1 <= value <= 1000
                       for value in self.evidence_ordinals)
                or tuple(sorted(set(self.evidence_ordinals)))
                != self.evidence_ordinals):
            raise AIOutputSchemaError()


class AIOutputSchemaPort(Protocol):
    schema_ref: str
    schema_version: int

    def validate(
        self, payload: object, *, allowed_source_ordinals: frozenset[int],
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
    ))
