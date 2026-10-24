from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable


class IndexBindingError(ValueError):
    """Base error for an invalid or conflicting PoC index binding."""


class IndexBindingConflict(IndexBindingError):
    """Raised when an existing index identity is rebound to another model."""


class EmbeddingDimensionMismatch(IndexBindingError):
    """Raised when a vector does not match the index binding dimension."""


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IndexBindingError(f"{field} is required")
    return normalized


@dataclass(frozen=True, slots=True)
class EmbeddingModelBinding:
    provider: str
    model: str
    dimension: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _required(self.provider, "provider"))
        object.__setattr__(self, "model", _required(self.model, "model"))
        if (
            not isinstance(self.dimension, int)
            or isinstance(self.dimension, bool)
            or self.dimension < 1
        ):
            raise IndexBindingError("dimension must be a positive integer")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "provider": self.provider,
            "model": self.model,
            "dimension": self.dimension,
        }


@dataclass(frozen=True, slots=True)
class IndexBinding:
    index_id: str
    index_version: str
    embedding: EmbeddingModelBinding

    def __post_init__(self) -> None:
        object.__setattr__(self, "index_id", _required(self.index_id, "index_id"))
        object.__setattr__(
            self, "index_version", _required(self.index_version, "index_version")
        )

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "index_id": self.index_id,
            "index_version": self.index_version,
            "embedding": self.embedding.to_dict(),
        }

    def validate_vector(self, vector: Iterable[float]) -> tuple[float, ...]:
        materialized = tuple(float(value) for value in vector)
        if len(materialized) != self.embedding.dimension:
            raise EmbeddingDimensionMismatch(
                "vector dimension does not match the index binding: "
                f"expected {self.embedding.dimension}, got {len(materialized)}"
            )
        return materialized


class IndexBindingRegistry:
    """In-memory PoC registry enforcing one immutable model binding per index id."""

    def __init__(self) -> None:
        self._bindings: dict[str, IndexBinding] = {}

    def register(self, binding: IndexBinding) -> IndexBinding:
        existing = self._bindings.get(binding.index_id)
        if existing is None:
            self._bindings[binding.index_id] = binding
            return binding
        if existing != binding:
            raise IndexBindingConflict(
                "an index id cannot be rebound; create a new index id and perform a full rebuild"
            )
        return existing

    def get(self, index_id: str) -> IndexBinding:
        try:
            return self._bindings[index_id]
        except KeyError as exc:
            raise IndexBindingError(f"unknown index_id: {index_id}") from exc

    def all(self) -> tuple[IndexBinding, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))
