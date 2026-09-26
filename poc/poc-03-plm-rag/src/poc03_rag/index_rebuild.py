from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .index_binding import IndexBinding, IndexBindingConflict, IndexBindingRegistry


class IndexRebuildError(RuntimeError):
    """Raised when a model-change rebuild does not meet the PoC contract."""


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
        raise IndexRebuildError("embedding provider network request failed") from exc


@dataclass(frozen=True, slots=True)
class IndexRebuildResult:
    old_index_id: str
    old_binding_fingerprint: str
    new_index_id: str
    new_binding_fingerprint: str
    source_record_count: int
    rebuilt_record_count: int
    unique_source_hash_count: int
    request_count: int
    reused_vector_count: int
    returned_dimension: int

    def to_sanitized_dict(self) -> dict[str, str | int | bool]:
        return {
            "old_index_id": self.old_index_id,
            "old_binding_fingerprint": self.old_binding_fingerprint,
            "new_index_id": self.new_index_id,
            "new_binding_fingerprint": self.new_binding_fingerprint,
            "source_record_count": self.source_record_count,
            "rebuilt_record_count": self.rebuilt_record_count,
            "unique_source_hash_count": self.unique_source_hash_count,
            "request_count": self.request_count,
            "reused_vector_count": self.reused_vector_count,
            "returned_dimension": self.returned_dimension,
            "old_index_mutation_rejected": True,
            "new_index_created": True,
            "full_rebuild_completed": self.source_record_count == self.rebuilt_record_count,
            "customer_content_uploaded": False,
            "input_text_committed": False,
            "embedding_values_committed": False,
            "api_key_committed": False,
        }


def validate_model_change_rebuild(
    *,
    old_binding: IndexBinding,
    new_binding: IndexBinding,
    texts: Iterable[str],
    base_url: str,
    api_key: str,
    max_batch_size: int,
    transport: Transport | None = None,
    timeout_seconds: float = 30.0,
) -> IndexRebuildResult:
    records = [text.strip() for text in texts]
    if not records or any(not text for text in records):
        raise IndexRebuildError("rebuild texts must be non-empty")
    if not base_url.strip() or not api_key.strip():
        raise IndexRebuildError("base_url and api_key are required")
    if max_batch_size < 1:
        raise IndexRebuildError("max_batch_size must be positive")
    if old_binding.index_id == new_binding.index_id:
        raise IndexRebuildError("model change requires a new index id")
    if old_binding.embedding == new_binding.embedding:
        raise IndexRebuildError("new index must use a different embedding binding")

    registry = IndexBindingRegistry()
    registry.register(old_binding)
    mutation_candidate = IndexBinding(
        index_id=old_binding.index_id,
        index_version=new_binding.index_version,
        embedding=new_binding.embedding,
    )
    try:
        registry.register(mutation_candidate)
    except IndexBindingConflict:
        pass
    else:
        raise IndexRebuildError("old index mutation was not rejected")
    registry.register(new_binding)

    sender = transport or _default_transport
    rebuilt_count = 0
    request_count = 0
    returned_dimension = 0
    url = base_url.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    for offset in range(0, len(records), max_batch_size):
        batch = records[offset : offset + max_batch_size]
        payload = {
            "model": new_binding.embedding.model,
            "input": batch,
            "dimensions": new_binding.embedding.dimension,
        }
        status_code, response_body = sender(
            url,
            headers,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            timeout_seconds,
        )
        request_count += 1
        if status_code >= 400:
            raise IndexRebuildError(f"embedding provider returned HTTP {status_code}")
        try:
            data = json.loads(response_body)["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise IndexRebuildError("embedding provider response is invalid") from exc
        if not isinstance(data, list) or len(data) != len(batch):
            raise IndexRebuildError("embedding provider returned an unexpected row count")
        for item in data:
            try:
                vector = item["embedding"]
            except (KeyError, TypeError) as exc:
                raise IndexRebuildError("embedding provider response is invalid") from exc
            if not isinstance(vector, list):
                raise IndexRebuildError("embedding provider response is invalid")
            new_binding.validate_vector(vector)
            returned_dimension = len(vector)
            rebuilt_count += 1

    return IndexRebuildResult(
        old_index_id=old_binding.index_id,
        old_binding_fingerprint=old_binding.fingerprint,
        new_index_id=new_binding.index_id,
        new_binding_fingerprint=new_binding.fingerprint,
        source_record_count=len(records),
        rebuilt_record_count=rebuilt_count,
        unique_source_hash_count=len(
            {hashlib.sha256(text.encode("utf-8")).hexdigest() for text in records}
        ),
        request_count=request_count,
        reused_vector_count=0,
        returned_dimension=returned_dimension,
    )
