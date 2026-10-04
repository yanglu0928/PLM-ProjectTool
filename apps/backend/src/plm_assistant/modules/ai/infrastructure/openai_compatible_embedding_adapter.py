"""Pinned OpenAI-compatible HTTPS Adapter for authorized Embedding batches."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
    AIEmbeddingSendProof,
    require_embedding_send,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
)

from .openai_compatible_adapter import (
    _MAX_KEY_BYTES,
    _PinnedOpenAIConnection,
    PinnedHttpsOpenAICompatibleAdapter,
    _canonical_json,
)


_REQUEST_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}\Z")


def _embedding_wire_body(
    route: AIProviderExecutionRoute, envelope: AIEmbeddingEnvelope,
) -> bytearray:
    try:
        envelope.__post_init__()
        value = json.loads(envelope.canonical_bytes.decode("utf-8"))
        if (type(value) is not dict
                or set(value) != {"input", "model", "schema_version"}
                or value["schema_version"] != "provider-neutral-embedding.v1"
                or value["model"] != {
                    "key": route.provider_model_key,
                    "revision": route.model_revision,
                }
                or type(value["input"]) is not list
                or len(value["input"]) != envelope.record_count
                or any(type(item) is not str or not item
                       for item in value["input"])):
            raise ValueError()
        return bytearray(_canonical_json({
            "encoding_format": "float",
            "input": value["input"],
            "model": route.provider_model_key,
        }))
    except Exception:
        raise AIProviderExecutionError("AI_EMBEDDING_ENVELOPE_REJECTED") from None


def _validate_embedding_response(
    value: object, *, envelope: AIEmbeddingEnvelope,
    route: AIProviderExecutionRoute,
) -> tuple[int | None, int]:
    if type(value) is not dict or "data" not in value:
        raise ValueError()
    if set(value) - {"data", "model", "object", "usage", "id"}:
        raise ValueError()
    if ("model" in value and value["model"] != route.provider_model_key
            or "object" in value and value["object"] != "list"
            or "id" in value and (
                type(value["id"]) is not str
                or _REQUEST_REF.fullmatch(value["id"]) is None)):
        raise ValueError()
    data = value["data"]
    if type(data) is not list or len(data) != envelope.record_count:
        raise ValueError()
    for expected, item in enumerate(data):
        if (type(item) is not dict
                or set(item) - {"embedding", "index", "object"}
                or set(item) < {"embedding", "index"}
                or item["index"] != expected
                or ("object" in item and item["object"] != "embedding")):
            raise ValueError()
        vector = item["embedding"]
        if (type(vector) is not list
                or len(vector) != envelope.embedding_dimension
                or any(type(number) not in {int, float}
                       or (type(number) is float and not math.isfinite(number))
                       or abs(number) > 1_000_000
                       for number in vector)):
            raise ValueError()
    usage = value.get("usage")
    if usage is None:
        return None, 0
    if (type(usage) is not dict
            or set(usage) != {"prompt_tokens", "total_tokens"}
            or type(usage["prompt_tokens"]) is not int
            or type(usage["total_tokens"]) is not int
            or not 0 <= usage["prompt_tokens"] <= usage["total_tokens"]
            or usage["total_tokens"] > 1_073_741_824):
        raise ValueError()
    return usage["prompt_tokens"], 0


class _PinnedOpenAIEmbeddingConnection(_PinnedOpenAIConnection):
    def send(self, envelope: AIEmbeddingEnvelope,
             key: memoryview) -> AIProviderResponse:
        if self._used:
            raise AIProviderExecutionError("AI_PROVIDER_REQUEST_REJECTED")
        self._used = True
        if (type(key) is not memoryview or not 1 <= len(key) <= _MAX_KEY_BYTES
                or any(not 33 <= value <= 126 for value in key)):
            raise AIProviderExecutionError("AI_PROVIDER_SECRET_REJECTED")
        body = _embedding_wire_body(self._route, envelope)
        request = bytearray()
        raw = bytearray()
        started = self._monotonic()
        try:
            request.extend(
                f"POST {self._path} HTTP/1.1\r\nHost: {self._hostname}\r\n"
                "Content-Type: application/json\r\nAccept: application/json\r\n"
                f"Content-Length: {len(body)}\r\nAuthorization: Bearer ".encode(
                    "ascii",
                )
            )
            request.extend(key)
            request.extend(b"\r\nConnection: close\r\n\r\n")
            request.extend(body)
            self._socket.settimeout(self._remaining())
            self._socket.sendall(request)
            raw = self._response_body()
            try:
                value = json.loads(raw.decode("utf-8"))
                input_tokens, output_tokens = _validate_embedding_response(
                    value, envelope=envelope, route=self._route,
                )
            except (UnicodeDecodeError, ValueError, TypeError, KeyError, IndexError):
                raise AIProviderExecutionError(
                    "AI_EMBEDDING_RESPONSE_REJECTED",
                ) from None
            observation = AIProviderResponseObservation(
                hashlib.sha256(raw).digest(), len(raw), input_tokens,
                output_tokens,
                max(0, int((self._monotonic() - started) * 1000)), "STOP",
            )
            response = AIProviderResponse(raw, observation)
            raw = bytearray()
            return response
        except AIProviderExecutionError:
            raise
        except OSError:
            raise AIProviderExecutionError("AI_PROVIDER_NETWORK_UNAVAILABLE") from None
        finally:
            body[:] = b"\x00" * len(body)
            request[:] = b"\x00" * len(request)
            raw[:] = b"\x00" * len(raw)


class PinnedHttpsOpenAICompatibleEmbeddingAdapter(
    PinnedHttpsOpenAICompatibleAdapter,
):
    """Same pinned transport policy as Chat, with strict vector semantics."""

    def send(
        self, *, route: AIProviderExecutionRoute, proof: AIEmbeddingSendProof,
        envelope: AIEmbeddingEnvelope, key: memoryview,
    ) -> AIProviderResponse:
        require_embedding_send(
            proof, route, envelope, now=datetime.now(timezone.utc),
        )
        return self._send_over_pinned_tls(
            route,
            lambda tls, hostname, path, deadline: _PinnedOpenAIEmbeddingConnection(
                tls, hostname=hostname, path=path, route=route,
                deadline=deadline, monotonic=self._monotonic,
            ).send(envelope, key),
        )
