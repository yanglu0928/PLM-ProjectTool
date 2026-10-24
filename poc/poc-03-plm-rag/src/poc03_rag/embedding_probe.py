from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class EmbeddingProbeError(RuntimeError):
    """Raised when an OpenAI-compatible embedding endpoint fails the PoC probe."""


@dataclass(frozen=True, slots=True)
class EmbeddingProbeResult:
    provider: str
    model: str
    requested_dimension: int
    returned_dimension: int
    input_count: int

    def to_sanitized_dict(self) -> dict[str, str | int | bool]:
        return {
            "provider": self.provider,
            "model": self.model,
            "requested_dimension": self.requested_dimension,
            "returned_dimension": self.returned_dimension,
            "input_count": self.input_count,
            "api_key_committed": False,
            "input_text_committed": False,
            "embedding_values_committed": False,
        }


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def _default_transport(
    url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, b""
    except URLError as exc:
        raise EmbeddingProbeError("embedding provider network request failed") from exc


def probe_openai_compatible_embedding(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    dimension: int,
    transport: Transport | None = None,
    timeout_seconds: float = 30.0,
) -> EmbeddingProbeResult:
    if not provider.strip() or not base_url.strip() or not api_key.strip() or not model.strip():
        raise EmbeddingProbeError("provider, base_url, api_key, and model are required")
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise EmbeddingProbeError("dimension must be a positive integer")

    payload: dict[str, Any] = {
        "model": model.strip(),
        "input": ["PLM PoC embedding connectivity probe"],
        "dimensions": dimension,
    }
    sender = transport or _default_transport
    url = base_url.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    status_code, response_body = sender(
        url,
        headers,
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        timeout_seconds,
    )
    if status_code >= 400:
        raise EmbeddingProbeError(
            f"embedding provider returned HTTP {status_code}"
        )
    try:
        body = json.loads(response_body)
        data = body["data"]
        vector = data[0]["embedding"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise EmbeddingProbeError("embedding provider response is invalid") from exc
    if not isinstance(data, list) or len(data) != 1 or not isinstance(vector, list):
        raise EmbeddingProbeError("embedding provider response is invalid")
    if len(vector) != dimension:
        raise EmbeddingProbeError(
            "embedding dimension mismatch: "
            f"expected {dimension}, got {len(vector)}"
        )
    return EmbeddingProbeResult(
        provider=provider.strip(),
        model=model.strip(),
        requested_dimension=dimension,
        returned_dimension=len(vector),
        input_count=len(data),
    )
