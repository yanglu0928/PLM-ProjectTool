from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.index_binding import EmbeddingModelBinding, IndexBinding  # noqa: E402
from poc03_rag.index_rebuild import (  # noqa: E402
    IndexRebuildError,
    validate_model_change_rebuild,
)


def make_binding(index_id: str, version: str, model: str, dimension: int) -> IndexBinding:
    return IndexBinding(
        index_id=index_id,
        index_version=version,
        embedding=EmbeddingModelBinding(
            provider="provider",
            model=model,
            dimension=dimension,
        ),
    )


class IndexRebuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = make_binding("index-v1", "v1", "model-a", 3)
        self.new = make_binding("index-v2", "v2", "model-b", 2)

    def test_full_rebuild_uses_new_index_and_batches_every_record(self) -> None:
        requests: list[dict[str, object]] = []

        def transport(_url: str, _headers: dict[str, str], body: bytes, _timeout: float):
            payload = json.loads(body)
            requests.append(payload)
            data = [
                {"index": index, "embedding": [0.1, 0.2]}
                for index, _text in enumerate(payload["input"])
            ]
            return 200, json.dumps({"data": data}).encode()

        result = validate_model_change_rebuild(
            old_binding=self.old,
            new_binding=self.new,
            texts=["one", "two", "three"],
            base_url="https://example.invalid/v1",
            api_key="secret",
            max_batch_size=2,
            transport=transport,
        )
        self.assertEqual(3, result.rebuilt_record_count)
        self.assertEqual(2, result.request_count)
        self.assertEqual(0, result.reused_vector_count)
        self.assertTrue(all(request["model"] == "model-b" for request in requests))
        self.assertNotIn("secret", str(result.to_sanitized_dict()))
        self.assertNotIn("[0.1, 0.2]", str(result.to_sanitized_dict()))
        self.assertFalse(result.to_sanitized_dict()["embedding_values_committed"])

    def test_model_change_cannot_reuse_old_index_id(self) -> None:
        new = make_binding("index-v1", "v2", "model-b", 2)
        with self.assertRaises(IndexRebuildError):
            validate_model_change_rebuild(
                old_binding=self.old,
                new_binding=new,
                texts=["one"],
                base_url="https://example.invalid/v1",
                api_key="secret",
                max_batch_size=1,
            )

    def test_partial_provider_response_fails_rebuild(self) -> None:
        def transport(_url: str, _headers: dict[str, str], _body: bytes, _timeout: float):
            return 200, json.dumps({"data": []}).encode()

        with self.assertRaises(IndexRebuildError):
            validate_model_change_rebuild(
                old_binding=self.old,
                new_binding=self.new,
                texts=["one"],
                base_url="https://example.invalid/v1",
                api_key="secret",
                max_batch_size=1,
                transport=transport,
            )

    def test_wrong_dimension_fails_rebuild(self) -> None:
        def transport(_url: str, _headers: dict[str, str], _body: bytes, _timeout: float):
            return 200, json.dumps({"data": [{"embedding": [0.1]}]}).encode()

        with self.assertRaises(ValueError):
            validate_model_change_rebuild(
                old_binding=self.old,
                new_binding=self.new,
                texts=["one"],
                base_url="https://example.invalid/v1",
                api_key="secret",
                max_batch_size=1,
                transport=transport,
            )


if __name__ == "__main__":
    unittest.main()
