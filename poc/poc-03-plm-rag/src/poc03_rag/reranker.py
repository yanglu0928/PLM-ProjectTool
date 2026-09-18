from __future__ import annotations

import json
from dataclasses import dataclass
from numbers import Real
from typing import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RerankerError(RuntimeError):
    """Raised when an external reranker request cannot be accepted."""

    def __init__(self, code: str, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class RerankerConfig:
    provider: str
    base_url: str
    model: str
    timeout_seconds: float = 15.0
    fail_open: bool = True
    instruct: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.base_url.strip() or not self.model.strip():
            raise ValueError("provider, base_url, and model are required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    candidate_id: str
    text: str

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.text.strip():
            raise ValueError("candidate_id and text are required")


@dataclass(frozen=True, slots=True)
class RerankedItem:
    candidate_id: str
    relevance_score: float | None


@dataclass(frozen=True, slots=True)
class RerankResult:
    provider: str
    model: str
    items: tuple[RerankedItem, ...]
    provider_used: bool
    degraded: bool
    error_code: str | None = None

    def to_sanitized_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "provider_used": self.provider_used,
            "degraded": self.degraded,
            "error_code": self.error_code,
            "result_count": len(self.items),
            "result_ids": [item.candidate_id for item in self.items],
            "scores": [item.relevance_score for item in self.items],
            "api_key_committed": False,
            "query_text_committed": False,
            "document_text_committed": False,
            "provider_response_body_committed": False,
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
    except (URLError, TimeoutError, OSError) as exc:
        raise RerankerError("NETWORK_ERROR", "reranker network request failed") from exc


def _validate_request(
    *, api_key: str, query: str, candidates: Sequence[RerankCandidate], top_n: int
) -> None:
    if not api_key.strip() or not query.strip():
        raise RerankerError("INVALID_REQUEST", "api_key and query are required")
    if not candidates or len(candidates) > 500:
        raise RerankerError("INVALID_REQUEST", "candidate count must be between 1 and 500")
    if top_n < 1 or top_n > len(candidates):
        raise RerankerError("INVALID_REQUEST", "top_n must be within candidate count")
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise RerankerError("INVALID_REQUEST", "candidate_id values must be unique")


def rerank_candidates(
    *,
    config: RerankerConfig,
    api_key: str,
    query: str,
    candidates: Sequence[RerankCandidate],
    top_n: int,
    transport: Transport | None = None,
) -> RerankResult:
    _validate_request(api_key=api_key, query=query, candidates=candidates, top_n=top_n)
    payload = {
        "model": config.model.strip(),
        "query": query.strip(),
        "documents": [candidate.text for candidate in candidates],
        "top_n": top_n,
    }
    if config.instruct and config.instruct.strip():
        payload["instruct"] = config.instruct.strip()
    sender = transport or _default_transport
    try:
        status_code, response_body = sender(
            config.base_url.rstrip("/") + "/reranks",
            {
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            },
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            config.timeout_seconds,
        )
    except RerankerError:
        raise
    except (TimeoutError, OSError) as exc:
        raise RerankerError("NETWORK_ERROR", "reranker network request failed") from exc
    if status_code >= 400:
        raise RerankerError(
            f"HTTP_{status_code}",
            f"reranker returned HTTP {status_code}",
            http_status=status_code,
        )
    try:
        response = json.loads(response_body)
        results = response.get("results")
        if results is None:
            results = response["output"]["results"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RerankerError("INVALID_RESPONSE", "reranker response is invalid") from exc
    if not isinstance(results, list) or len(results) != top_n:
        raise RerankerError("INVALID_RESPONSE", "reranker result count is invalid")

    ranked: list[RerankedItem] = []
    seen: set[int] = set()
    for result in results:
        if not isinstance(result, dict):
            raise RerankerError("INVALID_RESPONSE", "reranker result item is invalid")
        index = result.get("index")
        score = result.get("relevance_score")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= len(candidates)
            or index in seen
            or isinstance(score, bool)
            or not isinstance(score, Real)
        ):
            raise RerankerError("INVALID_RESPONSE", "reranker result item is invalid")
        seen.add(index)
        ranked.append(
            RerankedItem(
                candidate_id=candidates[index].candidate_id,
                relevance_score=float(score),
            )
        )
    return RerankResult(
        provider=config.provider.strip(),
        model=config.model.strip(),
        items=tuple(ranked),
        provider_used=True,
        degraded=False,
    )


def rerank_with_fallback(
    *,
    config: RerankerConfig,
    api_key: str,
    query: str,
    candidates: Sequence[RerankCandidate],
    top_n: int,
    transport: Transport | None = None,
) -> RerankResult:
    try:
        return rerank_candidates(
            config=config,
            api_key=api_key,
            query=query,
            candidates=candidates,
            top_n=top_n,
            transport=transport,
        )
    except RerankerError as exc:
        if not config.fail_open:
            raise
        return RerankResult(
            provider=config.provider.strip(),
            model=config.model.strip(),
            items=tuple(
                RerankedItem(candidate_id=candidate.candidate_id, relevance_score=None)
                for candidate in candidates[:top_n]
            ),
            provider_used=False,
            degraded=True,
            error_code=exc.code,
        )
