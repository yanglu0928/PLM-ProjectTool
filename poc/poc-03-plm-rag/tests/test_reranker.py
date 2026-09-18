from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.reranker import (  # noqa: E402
    RerankCandidate,
    RerankerConfig,
    RerankerError,
    rerank_candidates,
    rerank_with_fallback,
)


class RerankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = RerankerConfig(
            provider="test-provider",
            base_url="https://rerank.example.invalid/compatible-api/v1",
            model="test-rerank",
            timeout_seconds=2,
            instruct="Retrieve direct evidence for the requirement.",
        )
        self.candidates = (
            RerankCandidate("C-1", "first candidate"),
            RerankCandidate("C-2", "second candidate"),
            RerankCandidate("C-3", "third candidate"),
        )

    def test_success_maps_provider_indices_without_persisting_content(self) -> None:
        captured: dict[str, object] = {}

        def transport(url, headers, body, timeout):
            captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
            return 200, json.dumps(
                {
                    "results": [
                        {"index": 1, "relevance_score": 0.9},
                        {"index": 0, "relevance_score": 0.6},
                    ]
                }
            ).encode()

        result = rerank_candidates(
            config=self.config,
            api_key="test-secret-value",
            query="query text",
            candidates=self.candidates,
            top_n=2,
            transport=transport,
        )
        self.assertEqual("https://rerank.example.invalid/compatible-api/v1/reranks", captured["url"])
        self.assertEqual(["C-2", "C-1"], [item.candidate_id for item in result.items])
        self.assertEqual(
            "Retrieve direct evidence for the requirement.",
            captured["body"]["instruct"],
        )
        report = result.to_sanitized_dict()
        self.assertFalse(report["api_key_committed"])
        self.assertFalse(report["query_text_committed"])
        self.assertNotIn("test-secret-value", json.dumps(report))
        self.assertNotIn("query text", json.dumps(report))

    def test_dashscope_nested_response_is_supported(self) -> None:
        result = rerank_candidates(
            config=self.config,
            api_key="key",
            query="query",
            candidates=self.candidates,
            top_n=1,
            transport=lambda *_: (
                200,
                b'{"output":{"results":[{"index":2,"relevance_score":0.8}]}}',
            ),
        )
        self.assertEqual("C-3", result.items[0].candidate_id)

    def test_http_429_degrades_to_original_order(self) -> None:
        result = rerank_with_fallback(
            config=self.config,
            api_key="key",
            query="query",
            candidates=self.candidates,
            top_n=2,
            transport=lambda *_: (429, b'{"message":"rate limited"}'),
        )
        self.assertTrue(result.degraded)
        self.assertEqual("HTTP_429", result.error_code)
        self.assertEqual(["C-1", "C-2"], [item.candidate_id for item in result.items])

    def test_timeout_degrades_without_exposing_exception(self) -> None:
        def timeout_transport(*_):
            raise TimeoutError("private transport detail")

        result = rerank_with_fallback(
            config=self.config,
            api_key="key",
            query="query",
            candidates=self.candidates,
            top_n=1,
            transport=timeout_transport,
        )
        self.assertEqual("NETWORK_ERROR", result.error_code)
        self.assertNotIn("private", json.dumps(result.to_sanitized_dict()))

    def test_invalid_response_degrades(self) -> None:
        result = rerank_with_fallback(
            config=self.config,
            api_key="key",
            query="query",
            candidates=self.candidates,
            top_n=1,
            transport=lambda *_: (200, b'{"results":[]}'),
        )
        self.assertEqual("INVALID_RESPONSE", result.error_code)

    def test_fail_closed_propagates_error(self) -> None:
        config = RerankerConfig(
            provider="test-provider",
            base_url="https://rerank.example.invalid/v1",
            model="test-rerank",
            fail_open=False,
        )
        with self.assertRaisesRegex(RerankerError, "HTTP 503"):
            rerank_with_fallback(
                config=config,
                api_key="key",
                query="query",
                candidates=self.candidates,
                top_n=1,
                transport=lambda *_: (503, b""),
            )

    def test_duplicate_candidate_ids_are_rejected(self) -> None:
        candidates = (
            RerankCandidate("C-1", "first"),
            RerankCandidate("C-1", "duplicate"),
        )
        with self.assertRaisesRegex(RerankerError, "unique"):
            rerank_candidates(
                config=self.config,
                api_key="key",
                query="query",
                candidates=candidates,
                top_n=1,
                transport=lambda *_: (200, b"{}"),
            )


if __name__ == "__main__":
    unittest.main()
