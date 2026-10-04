from __future__ import annotations

import hashlib
import json
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingSendProof,
    AIEmbeddingSource,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.openai_compatible_embedding_adapter import (
    PinnedHttpsOpenAICompatibleEmbeddingAdapter,
    _PinnedOpenAIEmbeddingConnection,
)

class _Socket:
    def __init__(self, response: bytes):
        self.response = response
        self.sent_copy = b""
        self.sent_buffer = None
        self.timeout = None

    def settimeout(self, value): self.timeout = value
    def recv(self, size):
        value, self.response = self.response[:size], self.response[size:]
        return value
    def sendall(self, value):
        self.sent_copy, self.sent_buffer = bytes(value), value
    def close(self): pass


def _fixture(value):
    now = datetime.now(timezone.utc)
    route = AIProviderExecutionRoute(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        ProviderKind.OPENAI_COMPATIBLE, "endpoint.embedding.v1",
        "https://api.example.test/v1/embeddings",
        uuid.uuid4(), uuid.uuid4(), "text-embedding-v4", "PROVIDER_MANAGED",
        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED", 2_000_000, 3, 10, 20,
    )
    text = "PLM embedding".encode()
    envelope = AIEmbeddingEnvelopeBuilder().build(
        embedding_build_id=uuid.uuid4(),
        embedding_index_id=uuid.uuid4(),
        embedding_build_batch_id=uuid.uuid4(),
        batch_ordinal=1,
        provider_model_key=route.provider_model_key,
        model_revision=route.model_revision, embedding_dimension=768,
        sources=(AIEmbeddingSource(
            1, uuid.uuid4(), hashlib.sha256(text).digest(), text,
        ),),
    )
    proof = AIEmbeddingSendProof(
        uuid.uuid4(), envelope.embedding_build_id,
        envelope.embedding_build_batch_id, uuid.uuid4(), uuid.uuid4(),
        uuid.uuid4(), "GLOBAL", None, 1,
        provider_route_fingerprint(route), envelope.source_refs_fingerprint,
        envelope.payload_fingerprint, envelope.payload_bytes,
        envelope.input_tokens, now + timedelta(minutes=5),
    )
    payload = json.dumps(value, separators=(",", ":")).encode()
    response = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload
    )
    return route, envelope, proof, _Socket(response)


class OpenAICompatibleEmbeddingAdapterTests(unittest.TestCase):
    def valid_response(self):
        return {
            "data": [{
                "embedding": [0.0] * 768, "index": 0,
                "object": "embedding",
            }],
            "model": "text-embedding-v4", "object": "list",
            "usage": {"prompt_tokens": 12, "total_tokens": 12},
        }

    def test_exact_wire_request_and_strict_vector_response(self):
        route, envelope, _, sock = _fixture(self.valid_response())
        response = _PinnedOpenAIEmbeddingConnection(
            sock, hostname="api.example.test", path="/v1/embeddings",
            route=route, deadline=time.monotonic() + 20,
            monotonic=time.monotonic,
        ).send(envelope, memoryview(bytearray(b"synthetic-key")))
        head, body = sock.sent_copy.split(b"\r\n\r\n", 1)
        sent = json.loads(body)
        logical = json.loads(envelope.canonical_bytes)
        self.assertEqual(sent, {
            "encoding_format": "float", "input": logical["input"],
            "model": route.provider_model_key,
        })
        self.assertIn(b"Authorization: Bearer synthetic-key", head)
        self.assertTrue(all(value == 0 for value in sock.sent_buffer))
        self.assertEqual(response.observation.input_tokens, 12)
        response.close()

    def test_count_index_dimension_nonfinite_and_model_drift_are_rejected(self):
        cases = []
        value = self.valid_response(); value["data"] = []
        cases.append(value)
        value = self.valid_response(); value["data"][0]["index"] = 1
        cases.append(value)
        value = self.valid_response(); value["data"][0]["embedding"] = [0.0] * 767
        cases.append(value)
        value = self.valid_response(); value["data"][0]["embedding"][0] = float("nan")
        cases.append(value)
        value = self.valid_response(); value["model"] = "other-model"
        cases.append(value)
        for value in cases:
            route, envelope, _, sock = _fixture(value)
            with self.subTest(value=list(value)), self.assertRaises(
                    AIProviderExecutionError) as caught:
                _PinnedOpenAIEmbeddingConnection(
                    sock, hostname="api.example.test", path="/v1/embeddings",
                    route=route, deadline=time.monotonic() + 20,
                    monotonic=time.monotonic,
                ).send(envelope, memoryview(bytearray(b"synthetic-key")))
            self.assertEqual(caught.exception.code, "AI_EMBEDDING_RESPONSE_REJECTED")
            self.assertTrue(all(item == 0 for item in sock.sent_buffer))

    def test_private_dns_is_rejected_before_connect(self):
        route, envelope, proof, _ = _fixture(self.valid_response())
        connected = []
        adapter = PinnedHttpsOpenAICompatibleEmbeddingAdapter(
            address_resolver=lambda *_: ("8.8.8.8", "127.0.0.1"),
            connector=lambda *args: connected.append(args),
        )
        with self.assertRaises(AIProviderExecutionError) as caught:
            adapter.send(
                route=route, proof=proof, envelope=envelope,
                key=memoryview(bytearray(b"synthetic-key")),
            )
        self.assertEqual(caught.exception.code, "AI_PROVIDER_DESTINATION_REJECTED")
        self.assertEqual(connected, [])


if __name__ == "__main__":
    unittest.main()
