from __future__ import annotations

import hashlib
import json
import math
import unittest
import uuid

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingSource,
)
from plm_assistant.modules.ai.application.embedding_response_contract import (
    AIEmbeddingResponseError,
    parse_embedding_response,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind


def _facts(value, *, observed_input=7):
    text = b"synthetic"
    envelope = AIEmbeddingEnvelopeBuilder().build(
        embedding_build_id=uuid.uuid4(), embedding_index_id=uuid.uuid4(),
        embedding_build_batch_id=uuid.uuid4(), batch_ordinal=1,
        provider_model_key="embed-model", model_revision="rev-1",
        embedding_dimension=768,
        sources=(AIEmbeddingSource(
            1, uuid.uuid4(), hashlib.sha256(text).digest(), text,
        ),),
    )
    route = AIProviderExecutionRoute(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        ProviderKind.OPENAI_COMPATIBLE, "endpoint.embedding.v1",
        "https://example.test/v1/embeddings", uuid.uuid4(), uuid.uuid4(),
        "embed-model", "rev-1", "cn-beijing", "CUSTOMER_CONTENT",
        2_000_000, 3, 10, 20,
    )
    raw = bytearray(json.dumps(
        value, separators=(",", ":"), allow_nan=True,
    ).encode())
    response = AIProviderResponse(raw, AIProviderResponseObservation(
        hashlib.sha256(raw).digest(), len(raw), observed_input, 0, 4, "STOP",
    ))
    return envelope, route, response


def _valid():
    return {
        "id": "request-123", "object": "list", "model": "embed-model",
        "data": [{
            "object": "embedding", "index": 0,
            "embedding": [0.1] * 768,
        }],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


class AIEmbeddingResponseContractTests(unittest.TestCase):
    def test_parses_float32_vectors_and_deterministic_fingerprint(self):
        envelope, route, response = _facts(_valid())
        first = parse_embedding_response(
            response=response, envelope=envelope, route=route,
        )
        second = parse_embedding_response(
            response=response, envelope=envelope, route=route,
        )
        self.assertEqual(first.provider_request_ref, "request-123")
        self.assertEqual(first.vectors, second.vectors)
        self.assertEqual(len(first.vectors[0].values), 768)
        self.assertNotEqual(first.vectors[0].values[0], 0.1)
        self.assertNotIn("0.1", repr(first))
        response.close()

    def test_missing_provider_id_uses_response_fingerprint_reference(self):
        value = _valid()
        del value["id"]
        envelope, route, response = _facts(value)
        parsed = parse_embedding_response(
            response=response, envelope=envelope, route=route,
        )
        self.assertEqual(
            parsed.provider_request_ref,
            "sha256:" + response.observation.response_fingerprint.hex(),
        )
        response.close()

    def test_shape_model_index_vector_usage_and_id_drift_fail_closed(self):
        cases = []
        for mutate in (
            lambda value: value.update(model="other"),
            lambda value: value["data"][0].update(index=1),
            lambda value: value["data"][0].update(embedding=[0.1] * 767),
            lambda value: value["data"][0].update(
                embedding=[math.nan] * 768),
            lambda value: value.update(id="bad\nrequest"),
        ):
            value = _valid()
            mutate(value)
            cases.append(_facts(value))
        cases.append(_facts(_valid(), observed_input=8))
        for envelope, route, response in cases:
            with self.subTest(response=response), self.assertRaises(
                    AIEmbeddingResponseError):
                parse_embedding_response(
                    response=response, envelope=envelope, route=route,
                )
            response.close()


if __name__ == "__main__":
    unittest.main()
