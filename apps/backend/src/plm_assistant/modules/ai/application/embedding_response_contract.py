"""Deterministic, provider-neutral proof for one Embedding response."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import struct
from dataclasses import dataclass, field

from .embedding_execution_contract import AIEmbeddingEnvelope
from .provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    provider_route_fingerprint,
)


_REQUEST_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}\Z")
_VECTOR_DOMAIN = b"plm-embedding-vector-float32.v1\x00"


class AIEmbeddingResponseError(RuntimeError):
    def __init__(self, code: str = "AI_EMBEDDING_RESPONSE_REJECTED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AIEmbeddingVector:
    response_index: int
    values: tuple[float, ...] = field(repr=False)
    vector_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.response_index) is not int or self.response_index < 0
                or type(self.values) is not tuple
                or len(self.values) not in {768, 1024}
                or any(type(value) is not float or not math.isfinite(value)
                       or abs(value) > 1_000_000 for value in self.values)
                or type(self.vector_fingerprint) is not bytes
                or len(self.vector_fingerprint) != 32):
            raise AIEmbeddingResponseError()
        packed = b"".join(struct.pack("!f", value) for value in self.values)
        expected = hashlib.sha256(
            _VECTOR_DOMAIN + len(self.values).to_bytes(4, "big") + packed,
        ).digest()
        if not hmac.compare_digest(expected, self.vector_fingerprint):
            raise AIEmbeddingResponseError()


@dataclass(frozen=True, slots=True)
class ParsedAIEmbeddingResponse:
    provider_request_ref: str
    route_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    response_fingerprint: bytes = field(repr=False)
    response_bytes: int
    usage_input_tokens: int | None
    latency_ms: int
    vectors: tuple[AIEmbeddingVector, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.provider_request_ref) is not str
                or _REQUEST_REF.fullmatch(self.provider_request_ref) is None
                or type(self.route_fingerprint) is not bytes
                or len(self.route_fingerprint) != 32
                or type(self.payload_fingerprint) is not bytes
                or len(self.payload_fingerprint) != 32
                or type(self.source_refs_fingerprint) is not bytes
                or len(self.source_refs_fingerprint) != 32
                or type(self.response_fingerprint) is not bytes
                or len(self.response_fingerprint) != 32
                or type(self.response_bytes) is not int
                or not 1 <= self.response_bytes <= 100_000_000
                or (self.usage_input_tokens is not None and (
                    type(self.usage_input_tokens) is not int
                    or not 0 <= self.usage_input_tokens <= 1_073_741_824))
                or type(self.latency_ms) is not int
                or not 0 <= self.latency_ms <= 86_400_000
                or type(self.vectors) is not tuple or not self.vectors
                or any(type(value) is not AIEmbeddingVector
                       for value in self.vectors)
                or tuple(value.response_index for value in self.vectors)
                != tuple(range(len(self.vectors)))):
            raise AIEmbeddingResponseError()
        for value in self.vectors:
            value.__post_init__()


def _vector(index: int, value: object,
            dimension: int) -> AIEmbeddingVector:
    if (type(value) is not list or len(value) != dimension
            or any(type(number) not in {int, float}
                   or not math.isfinite(float(number))
                   or abs(float(number)) > 1_000_000 for number in value)):
        raise AIEmbeddingResponseError()
    try:
        packed_values = tuple(
            struct.unpack("!f", struct.pack("!f", float(number)))[0]
            for number in value
        )
        packed = b"".join(struct.pack("!f", number) for number in packed_values)
    except (OverflowError, struct.error, ValueError):
        raise AIEmbeddingResponseError() from None
    fingerprint = hashlib.sha256(
        _VECTOR_DOMAIN + dimension.to_bytes(4, "big") + packed,
    ).digest()
    return AIEmbeddingVector(index, packed_values, fingerprint)


def parse_embedding_response(*, response: AIProviderResponse,
                             envelope: AIEmbeddingEnvelope,
                             route: AIProviderExecutionRoute
                             ) -> ParsedAIEmbeddingResponse:
    if (type(response) is not AIProviderResponse
            or type(envelope) is not AIEmbeddingEnvelope
            or type(route) is not AIProviderExecutionRoute):
        raise AIEmbeddingResponseError()
    try:
        envelope.__post_init__()
        route.__post_init__()
        response.observation.__post_init__()
        raw = response.view().tobytes()
        if (len(raw) != response.observation.response_bytes
                or not hmac.compare_digest(
                    hashlib.sha256(raw).digest(),
                    response.observation.response_fingerprint)):
            raise AIEmbeddingResponseError()
        value = json.loads(raw)
        if (type(value) is not dict or set(value) - {
                "data", "model", "object", "usage", "id"}
                or set(value) < {"data"}
                or ("model" in value
                    and value["model"] != route.provider_model_key)
                or ("object" in value and value["object"] != "list")):
            raise AIEmbeddingResponseError()
        data = value["data"]
        if type(data) is not list or len(data) != envelope.record_count:
            raise AIEmbeddingResponseError()
        vectors = []
        for expected, item in enumerate(data):
            if (type(item) is not dict
                    or set(item) - {"embedding", "index", "object"}
                    or set(item) < {"embedding", "index"}
                    or item["index"] != expected
                    or ("object" in item and item["object"] != "embedding")):
                raise AIEmbeddingResponseError()
            vectors.append(_vector(
                expected, item["embedding"], envelope.embedding_dimension,
            ))
        usage = value.get("usage")
        if usage is None:
            usage_input = None
        elif (type(usage) is not dict
              or set(usage) != {"prompt_tokens", "total_tokens"}
              or type(usage["prompt_tokens"]) is not int
              or type(usage["total_tokens"]) is not int
              or not 0 <= usage["prompt_tokens"] <= usage["total_tokens"]
              or usage["total_tokens"] > 1_073_741_824):
            raise AIEmbeddingResponseError()
        else:
            usage_input = usage["prompt_tokens"]
        observation = response.observation
        if (observation.input_tokens != usage_input
                or observation.output_tokens != 0
                or observation.finish_reason != "STOP"):
            raise AIEmbeddingResponseError()
        request_ref = value.get("id")
        if request_ref is None:
            request_ref = "sha256:" + observation.response_fingerprint.hex()
        if type(request_ref) is not str or _REQUEST_REF.fullmatch(request_ref) is None:
            raise AIEmbeddingResponseError()
        result = ParsedAIEmbeddingResponse(
            request_ref, provider_route_fingerprint(route),
            envelope.payload_fingerprint, envelope.source_refs_fingerprint,
            observation.response_fingerprint,
            observation.response_bytes, usage_input,
            observation.latency_ms, tuple(vectors),
        )
        result.__post_init__()
        return result
    except AIEmbeddingResponseError:
        raise
    except (AIProviderExecutionError, UnicodeDecodeError, json.JSONDecodeError,
            TypeError, ValueError, KeyError, IndexError):
        raise AIEmbeddingResponseError() from None
