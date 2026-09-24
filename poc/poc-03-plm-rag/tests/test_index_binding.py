from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.index_binding import (  # noqa: E402
    EmbeddingDimensionMismatch,
    EmbeddingModelBinding,
    IndexBinding,
    IndexBindingConflict,
    IndexBindingError,
    IndexBindingRegistry,
)


def binding(
    *,
    index_id: str = "plm-rag-poc03-v1",
    model: str = "qwen3.7-text-embedding",
    dimension: int = 1024,
) -> IndexBinding:
    return IndexBinding(
        index_id=index_id,
        index_version="v1",
        embedding=EmbeddingModelBinding(
            provider="aliyun-model-studio-openai-compatible",
            model=model,
            dimension=dimension,
        ),
    )


class IndexBindingTests(unittest.TestCase):
    def test_binding_requires_complete_model_identity(self) -> None:
        with self.assertRaises(IndexBindingError):
            EmbeddingModelBinding(provider="", model="model", dimension=1024)
        with self.assertRaises(IndexBindingError):
            EmbeddingModelBinding(provider="provider", model="", dimension=1024)
        with self.assertRaises(IndexBindingError):
            EmbeddingModelBinding(provider="provider", model="model", dimension=0)

    def test_same_binding_registration_is_idempotent(self) -> None:
        registry = IndexBindingRegistry()
        first = registry.register(binding())
        second = registry.register(binding())
        self.assertIs(first, second)
        self.assertEqual(1, len(registry.all()))

    def test_existing_index_cannot_change_model_or_dimension(self) -> None:
        registry = IndexBindingRegistry()
        registry.register(binding())
        with self.assertRaises(IndexBindingConflict):
            registry.register(binding(model="another-model"))
        with self.assertRaises(IndexBindingConflict):
            registry.register(binding(dimension=768))

    def test_new_model_must_use_a_new_index_identity(self) -> None:
        registry = IndexBindingRegistry()
        registry.register(binding())
        replacement = registry.register(
            binding(index_id="plm-rag-poc03-v2", model="another-model", dimension=768)
        )
        self.assertEqual(2, len(registry.all()))
        self.assertEqual("plm-rag-poc03-v2", replacement.index_id)

    def test_vector_dimension_must_match_binding(self) -> None:
        small = binding(dimension=3)
        self.assertEqual((0.1, 0.2, 0.3), small.validate_vector([0.1, 0.2, 0.3]))
        with self.assertRaises(EmbeddingDimensionMismatch):
            small.validate_vector([0.1, 0.2])

    def test_fingerprint_is_deterministic_and_binding_sensitive(self) -> None:
        self.assertEqual(binding().fingerprint, binding().fingerprint)
        self.assertNotEqual(binding().fingerprint, binding(dimension=768).fingerprint)


if __name__ == "__main__":
    unittest.main()
