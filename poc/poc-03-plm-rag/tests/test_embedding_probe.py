from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.embedding_probe import (  # noqa: E402
    EmbeddingProbeError,
    probe_openai_compatible_embedding,
)


class EmbeddingProbeTests(unittest.TestCase):
    def test_success_records_only_sanitized_metadata(self) -> None:
        test_credential = "unit-test-credential"

        def handler(
            url: str, headers: dict[str, str], content: bytes, timeout: float
        ) -> tuple[int, bytes]:
            body = json.loads(content)
            self.assertEqual("Bearer unit-test-credential", headers["Authorization"])
            self.assertEqual(
                "https://embedding.example.invalid/v1/embeddings", url
            )
            self.assertEqual(3, body["dimensions"])
            return (
                200,
                json.dumps(
                    {"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]}
                ).encode(),
            )

        result = probe_openai_compatible_embedding(
            provider="provider",
            base_url="https://embedding.example.invalid/v1",
            api_key=test_credential,
            model="model",
            dimension=3,
            transport=handler,
        )
        report = result.to_sanitized_dict()
        self.assertEqual(3, report["returned_dimension"])
        self.assertNotIn("embedding", report)
        self.assertNotIn("api_key", report)

    def test_dimension_mismatch_is_rejected(self) -> None:
        test_credential = "unit-test-credential"
        transport = lambda *_: (
            200,
            json.dumps({"data": [{"embedding": [0.1, 0.2]}]}).encode(),
        )
        with self.assertRaisesRegex(EmbeddingProbeError, "dimension mismatch"):
            probe_openai_compatible_embedding(
                provider="provider",
                base_url="https://embedding.example.invalid/v1",
                api_key=test_credential,
                model="model",
                dimension=3,
                transport=transport,
            )

    def test_http_error_does_not_expose_provider_body(self) -> None:
        test_credential = "unit-test-credential"
        transport = lambda *_: (401, b'{"error":"sensitive-provider-detail"}')
        with self.assertRaisesRegex(EmbeddingProbeError, "HTTP 401") as raised:
            probe_openai_compatible_embedding(
                provider="provider",
                base_url="https://embedding.example.invalid/v1",
                api_key=test_credential,
                model="model",
                dimension=3,
                transport=transport,
            )
        self.assertNotIn("sensitive-provider-detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
