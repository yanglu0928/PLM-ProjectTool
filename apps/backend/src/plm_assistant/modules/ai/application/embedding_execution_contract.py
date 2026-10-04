"""Provider-neutral, deterministic Embedding request and send contract."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    provider_route_fingerprint,
)


_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_ESTIMATOR = "utf8-byte-upper-bound.embedding.v1"
_SCHEMA = "provider-neutral-embedding.v1"


class AIEmbeddingExecutionError(RuntimeError):
    def __init__(self, code: str = "AI_EMBEDDING_EXECUTION_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise AIEmbeddingExecutionError() from None


@dataclass(frozen=True, slots=True)
class AIEmbeddingSource:
    source_ordinal: int
    chunk_id: uuid.UUID
    text_fingerprint: bytes = field(repr=False)
    content_utf8: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.source_ordinal) is not int
                or not 1 <= self.source_ordinal <= 1_000_000_000
                or not _id(self.chunk_id) or not _digest(self.text_fingerprint)
                or type(self.content_utf8) is not bytes
                or not 1 <= len(self.content_utf8) <= 65_535):
            raise AIEmbeddingExecutionError("AI_EMBEDDING_SOURCE_INVALID")
        try:
            text = self.content_utf8.decode("utf-8")
        except UnicodeDecodeError:
            raise AIEmbeddingExecutionError("AI_EMBEDDING_SOURCE_INVALID") from None
        if not text.strip() or "\x00" in text:
            raise AIEmbeddingExecutionError("AI_EMBEDDING_SOURCE_INVALID")


@dataclass(frozen=True, slots=True)
class AIEmbeddingEnvelope:
    embedding_build_id: uuid.UUID
    embedding_build_batch_id: uuid.UUID
    provider_model_key: str
    model_revision: str
    source_refs_fingerprint: bytes = field(repr=False)
    source_text_fingerprints: tuple[bytes, ...] = field(repr=False)
    canonical_bytes: bytes = field(repr=False)
    record_count: int
    input_tokens: int
    token_estimator_ref: str = _ESTIMATOR

    def __post_init__(self) -> None:
        if (not _id(self.embedding_build_id)
                or not _id(self.embedding_build_batch_id)
                or type(self.provider_model_key) is not str
                or _MODEL.fullmatch(self.provider_model_key) is None
                or type(self.model_revision) is not str
                or _MODEL.fullmatch(self.model_revision) is None
                or not _digest(self.source_refs_fingerprint)
                or type(self.source_text_fingerprints) is not tuple
                or not self.source_text_fingerprints
                or any(not _digest(value)
                       for value in self.source_text_fingerprints)
                or type(self.canonical_bytes) is not bytes
                or not 1 <= len(self.canonical_bytes) <= 100_000_000
                or type(self.record_count) is not int
                or self.record_count != len(self.source_text_fingerprints)
                or not 1 <= self.record_count <= 1_000
                or type(self.input_tokens) is not int
                or not 1 <= self.input_tokens <= 1_048_576
                or self.token_estimator_ref != _ESTIMATOR):
            raise AIEmbeddingExecutionError("AI_EMBEDDING_ENVELOPE_INVALID")
        try:
            value = json.loads(self.canonical_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, TypeError):
            raise AIEmbeddingExecutionError("AI_EMBEDDING_ENVELOPE_INVALID") from None
        expected_model = {
            "key": self.provider_model_key, "revision": self.model_revision,
        }
        inputs = value.get("input") if type(value) is dict else None
        if (type(value) is not dict or set(value) != {
                "input", "model", "schema_version"}
                or value["schema_version"] != _SCHEMA
                or value["model"] != expected_model
                or type(inputs) is not list or len(inputs) != self.record_count
                or any(type(item) is not str or not item.strip() or "\x00" in item
                       for item in inputs)
                or _canonical(value) != self.canonical_bytes):
            raise AIEmbeddingExecutionError("AI_EMBEDDING_ENVELOPE_INVALID")

    @property
    def payload_fingerprint(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes).digest()

    @property
    def payload_bytes(self) -> int:
        return len(self.canonical_bytes)


class AIEmbeddingEnvelopeBuilder:
    """Build the exact logical payload authorized for one external Batch."""

    def build(self, *, embedding_build_id: uuid.UUID,
              embedding_build_batch_id: uuid.UUID,
              provider_model_key: str, model_revision: str,
              sources: tuple[AIEmbeddingSource, ...]) -> AIEmbeddingEnvelope:
        if type(sources) is not tuple or not 1 <= len(sources) <= 1_000:
            raise AIEmbeddingExecutionError("AI_EMBEDDING_SOURCE_INVALID")
        texts: list[str] = []
        canonical_sources: list[str] = []
        fingerprints: list[bytes] = []
        expected = sources[0].source_ordinal if sources else 0
        input_tokens = 8
        for source in sources:
            if type(source) is not AIEmbeddingSource:
                raise AIEmbeddingExecutionError("AI_EMBEDDING_SOURCE_INVALID")
            source.__post_init__()
            if source.source_ordinal != expected:
                raise AIEmbeddingExecutionError("AI_EMBEDDING_SOURCE_INVALID")
            expected += 1
            text = source.content_utf8.decode("utf-8")
            texts.append(text)
            fingerprints.append(source.text_fingerprint)
            canonical_sources.append(
                f"{source.source_ordinal}:{source.chunk_id}:"
                f"{source.text_fingerprint.hex()}"
            )
            input_tokens += len(source.content_utf8)
        if input_tokens > 1_048_576:
            raise AIEmbeddingExecutionError("AI_EMBEDDING_TOKEN_LIMIT_EXCEEDED")
        canonical_bytes = _canonical({
            "input": texts,
            "model": {"key": provider_model_key, "revision": model_revision},
            "schema_version": _SCHEMA,
        })
        result = AIEmbeddingEnvelope(
            embedding_build_id, embedding_build_batch_id,
            provider_model_key, model_revision,
            hashlib.sha256("\n".join(canonical_sources).encode("utf-8")).digest(),
            tuple(fingerprints), canonical_bytes, len(sources), input_tokens,
        )
        result.__post_init__()
        return result


@dataclass(frozen=True, slots=True)
class AIEmbeddingSendProof:
    job_id: uuid.UUID
    embedding_build_id: uuid.UUID
    embedding_build_batch_id: uuid.UUID
    egress_authorization_ref: uuid.UUID
    fencing_token: int
    route_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    payload_bytes: int
    input_tokens: int
    valid_until: datetime

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.job_id, self.embedding_build_id,
                self.embedding_build_batch_id, self.egress_authorization_ref))
                or self.fencing_token != 1
                or not all(_digest(value) for value in (
                    self.route_fingerprint, self.source_refs_fingerprint,
                    self.payload_fingerprint))
                or type(self.payload_bytes) is not int or self.payload_bytes < 1
                or type(self.input_tokens) is not int or self.input_tokens < 1
                or not isinstance(self.valid_until, datetime)
                or self.valid_until.tzinfo is None
                or self.valid_until.utcoffset() is None):
            raise AIEmbeddingExecutionError("AI_EMBEDDING_SEND_PROOF_INVALID")


def require_embedding_send(proof: AIEmbeddingSendProof,
                           route: AIProviderExecutionRoute,
                           envelope: AIEmbeddingEnvelope, *, now: datetime
                           ) -> AIEmbeddingSendProof:
    try:
        proof.__post_init__()
        route.__post_init__()
        envelope.__post_init__()
    except Exception:
        raise AIEmbeddingExecutionError("AI_EMBEDDING_SEND_NOT_AUTHORIZED") from None
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None
            or now.astimezone(timezone.utc) >= proof.valid_until.astimezone(timezone.utc)
            or proof.embedding_build_id != envelope.embedding_build_id
            or proof.embedding_build_batch_id != envelope.embedding_build_batch_id
            or route.ai_model_id.int == 0
            or route.provider_model_key != envelope.provider_model_key
            or route.model_revision != envelope.model_revision
            or not hmac.compare_digest(
                proof.route_fingerprint, provider_route_fingerprint(route))
            or not hmac.compare_digest(
                proof.source_refs_fingerprint, envelope.source_refs_fingerprint)
            or not hmac.compare_digest(
                proof.payload_fingerprint, envelope.payload_fingerprint)
            or proof.payload_bytes != envelope.payload_bytes
            or proof.input_tokens != envelope.input_tokens):
        raise AIEmbeddingExecutionError("AI_EMBEDDING_SEND_NOT_AUTHORIZED")
    return proof


class AIEmbeddingProviderAdapterPort(Protocol):
    def send(self, *, route: AIProviderExecutionRoute,
             proof: AIEmbeddingSendProof, envelope: AIEmbeddingEnvelope,
             key: memoryview) -> AIProviderResponse: ...
