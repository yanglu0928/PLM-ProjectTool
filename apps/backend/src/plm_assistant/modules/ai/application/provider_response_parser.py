"""Bounded OpenAI-compatible wrapper parser and trusted output validation."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field

from .output_schema import (
    AIOutputSchemaError,
    AIOutputSchemaRegistry,
)
from .provider_execution_contract import AIProviderResponse
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AIProviderResponseParseError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_RESPONSE_INVALID") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParsedAISuggestion:
    ai_task_id: uuid.UUID
    ai_invocation_id: uuid.UUID
    project_id: uuid.UUID
    output_schema_ref: str
    schema_version: int
    canonical_payload_json: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    evidence_ordinals: tuple[int, ...]
    response_fingerprint: bytes = field(repr=False)
    usage_input_tokens: int | None
    usage_output_tokens: int | None
    latency_ms: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                    self.ai_task_id, self.ai_invocation_id, self.project_id))
                or type(self.output_schema_ref) is not str
                or not self.output_schema_ref
                or type(self.schema_version) is not int or self.schema_version < 1
                or type(self.canonical_payload_json) is not bytes
                or not 2 <= len(self.canonical_payload_json) <= 1_048_576
                or any(type(value) is not bytes or len(value) != 32 for value in (
                    self.payload_fingerprint, self.response_fingerprint))
                or type(self.evidence_ordinals) is not tuple
                or not self.evidence_ordinals
                or type(self.latency_ms) is not int or self.latency_ms < 0):
            raise AIProviderResponseParseError()


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON number")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _bounded_json(raw: bytes | str, *, maximum_bytes: int,
                  maximum_depth: int, maximum_nodes: int) -> object:
    if type(raw) is bytes:
        if not raw or len(raw) > maximum_bytes:
            raise AIProviderResponseParseError()
        source: bytes | str = raw
    elif type(raw) is str:
        try:
            size = len(raw.encode("utf-8"))
        except UnicodeError:
            raise AIProviderResponseParseError() from None
        if not raw or size > maximum_bytes:
            raise AIProviderResponseParseError()
        source = raw
    else:
        raise AIProviderResponseParseError()
    try:
        value = json.loads(
            source, object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeError):
        raise AIProviderResponseParseError() from None
    stack = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > maximum_nodes or depth > maximum_depth:
            raise AIProviderResponseParseError()
        if type(current) is dict:
            if len(current) > 256 or any(
                    type(key) is not str or not key or len(key.encode("utf-8")) > 128
                    for key in current):
                raise AIProviderResponseParseError()
            stack.extend((item, depth + 1) for item in current.values())
        elif type(current) is list:
            if len(current) > 256:
                raise AIProviderResponseParseError()
            stack.extend((item, depth + 1) for item in current)
        elif type(current) is str:
            try:
                if len(current.encode("utf-8")) > maximum_bytes:
                    raise AIProviderResponseParseError()
            except UnicodeError:
                raise AIProviderResponseParseError() from None
        elif type(current) is int:
            if not -9_223_372_036_854_775_808 <= current <= 9_223_372_036_854_775_807:
                raise AIProviderResponseParseError()
        elif type(current) is float:
            if not math.isfinite(current) or abs(current) > 1e308:
                raise AIProviderResponseParseError()
        elif current is not None and type(current) is not bool:
            raise AIProviderResponseParseError()
    return value


class AIProviderSuggestionParser:
    def __init__(self, *, schemas: AIOutputSchemaRegistry) -> None:
        if type(schemas) is not AIOutputSchemaRegistry:
            raise ValueError("trusted AI output schema registry required")
        self._schemas = schemas

    def parse(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, response: AIProviderResponse,
    ) -> ParsedAISuggestion:
        if (type(prepared) is not PreparedAITaskInvocation
                or type(begun) is not BegunAITaskInvocation
                or type(response) is not AIProviderResponse):
            raise AIProviderResponseParseError()
        try:
            prepared.__post_init__()
            begun.__post_init__()
            if begun.grant != prepared.grant:
                raise AIProviderResponseParseError()
            observation = response.observation
            observation.__post_init__()
            if observation.finish_reason != "STOP":
                raise AIProviderResponseParseError(
                    "AI_PROVIDER_RESPONSE_INCOMPLETE",
                )
            view = response.view()
            try:
                wrapper = _bounded_json(
                    bytes(view), maximum_bytes=1_000_000,
                    maximum_depth=12, maximum_nodes=4096,
                )
            finally:
                view.release()
            if type(wrapper) is not dict:
                raise AIProviderResponseParseError()
            choices = wrapper.get("choices")
            if type(choices) is not list or len(choices) != 1:
                raise AIProviderResponseParseError()
            choice = choices[0]
            if type(choice) is not dict:
                raise AIProviderResponseParseError()
            message = choice.get("message")
            if type(message) is not dict or type(message.get("content")) is not str:
                raise AIProviderResponseParseError()
            payload = _bounded_json(
                message["content"], maximum_bytes=1_048_576,
                maximum_depth=12, maximum_nodes=4096,
            )
            grant = prepared.grant
            schema = self._schemas.resolve(
                grant.output_schema_ref, grant.schema_version,
            )
            validated = schema.validate(
                payload,
                allowed_source_ordinals=frozenset(
                    item.ordinal for item in grant.input_refs
                ),
            )
            return ParsedAISuggestion(
                grant.ai_task_id, begun.ai_invocation_id, grant.project_id,
                grant.output_schema_ref, grant.schema_version,
                validated.canonical_json,
                hashlib.sha256(validated.canonical_json).digest(),
                validated.evidence_ordinals,
                observation.response_fingerprint,
                observation.input_tokens, observation.output_tokens,
                observation.latency_ms,
            )
        except AIProviderResponseParseError:
            raise
        except AIOutputSchemaError as error:
            raise AIProviderResponseParseError(error.code) from None
        except Exception:
            raise AIProviderResponseParseError() from None
