from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingExecutionError,
    AIEmbeddingSendProof,
    AIEmbeddingSource,
    require_embedding_send,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind


class _SyntheticEmbeddingAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, *, route, proof, envelope, key):
        require_embedding_send(
            proof, route, envelope,
            now=datetime(2026, 10, 4, 14, tzinfo=timezone.utc),
        )
        if bytes(key) != b"synthetic-key":
            raise AIEmbeddingExecutionError()
        self.calls += 1
        body = bytearray(b'{"data":[{"embedding":[0.0,1.0],"index":0}]}')
        return AIProviderResponse(body, AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body),
            envelope.input_tokens, 0, 1, "STOP",
        ))


class AIEmbeddingExecutionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 4, 14, tzinfo=timezone.utc)
        self.build_id, self.index_id, self.batch_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        )
        self.sources = tuple(
            AIEmbeddingSource(i, uuid.uuid4(), hashlib.sha256(text).digest(), text)
            for i, text in enumerate(("PLM需求".encode(), "PLM交付".encode()), 3)
        )
        self.envelope = AIEmbeddingEnvelopeBuilder().build(
            embedding_build_id=self.build_id,
            embedding_index_id=self.index_id,
            embedding_build_batch_id=self.batch_id,
            batch_ordinal=1,
            provider_model_key="text-embedding-v4",
            model_revision="PROVIDER_MANAGED", embedding_dimension=1024,
            sources=self.sources,
        )
        self.route = AIProviderExecutionRoute(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            ProviderKind.OPENAI_COMPATIBLE, "BAILIAN_EMBEDDING_V1",
            "https://example.com/v1/embeddings", uuid.uuid4(), uuid.uuid4(),
            "text-embedding-v4", "PROVIDER_MANAGED", "cn-beijing",
            "CUSTOMER_CONTENT", 1_000_000, 5, 20, 30,
        )
        self.proof = AIEmbeddingSendProof(
            uuid.uuid4(), self.build_id, self.batch_id, uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), "GLOBAL", None, 1,
            provider_route_fingerprint(self.route),
            self.envelope.source_refs_fingerprint,
            self.envelope.payload_fingerprint, self.envelope.payload_bytes,
            self.envelope.input_tokens, self.now + timedelta(minutes=1),
        )

    def test_deterministic_envelope_and_synthetic_adapter_boundary(self) -> None:
        same = AIEmbeddingEnvelopeBuilder().build(
            embedding_build_id=self.build_id,
            embedding_index_id=self.index_id,
            embedding_build_batch_id=self.batch_id,
            batch_ordinal=1,
            provider_model_key="text-embedding-v4",
            model_revision="PROVIDER_MANAGED", embedding_dimension=1024,
            sources=self.sources,
        )
        self.assertEqual(same.canonical_bytes, self.envelope.canonical_bytes)
        adapter = _SyntheticEmbeddingAdapter()
        with adapter.send(
            route=self.route, proof=self.proof, envelope=self.envelope,
            key=memoryview(bytearray(b"synthetic-key")),
        ) as response:
            self.assertIn(b"embedding", bytes(response.view()))
        self.assertEqual(adapter.calls, 1)

    def test_route_payload_source_expiry_and_order_drift_fail_closed(self) -> None:
        cases = (
            (replace(self.proof, payload_fingerprint=b"x" * 32), self.route,
             self.envelope, self.now),
            (replace(self.proof, source_refs_fingerprint=b"x" * 32), self.route,
             self.envelope, self.now),
            (replace(self.proof, route_fingerprint=b"x" * 32), self.route,
             self.envelope, self.now),
            (self.proof, self.route, self.envelope,
             self.proof.valid_until),
        )
        for proof, route, envelope, now in cases:
            with self.subTest(proof=proof), self.assertRaises(
                    AIEmbeddingExecutionError):
                require_embedding_send(proof, route, envelope, now=now)
        with self.assertRaises(AIEmbeddingExecutionError):
            AIEmbeddingEnvelopeBuilder().build(
                embedding_build_id=self.build_id,
                embedding_index_id=self.index_id,
                embedding_build_batch_id=self.batch_id,
                batch_ordinal=1,
                provider_model_key="text-embedding-v4",
                model_revision="PROVIDER_MANAGED",
                embedding_dimension=1024,
                sources=(self.sources[1], self.sources[0]),
            )

    def test_sensitive_source_and_envelope_bytes_are_hidden_from_repr(self) -> None:
        self.assertNotIn("PLM需求", repr(self.sources[0]))
        self.assertNotIn("PLM需求", repr(self.envelope))
        self.assertNotIn(self.envelope.payload_fingerprint.hex(), repr(self.proof))


if __name__ == "__main__":
    unittest.main()
