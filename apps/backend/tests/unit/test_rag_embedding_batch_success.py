from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingSendProof,
    AIEmbeddingSource,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.embedding_response_contract import (
    parse_embedding_response,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.rag.application.embedding_batch_success import (
    PublishedRAGEmbeddingBatch,
    RAGEmbeddingBatchSuccessError,
    RAGEmbeddingBatchSuccessService,
)


def _facts():
    now = datetime(2026, 10, 4, 18, tzinfo=timezone.utc)
    job, build, index, batch = (uuid.uuid4() for _ in range(4))
    actor, trace, authorization = (uuid.uuid4() for _ in range(3))
    text = b"synthetic"
    envelope = AIEmbeddingEnvelopeBuilder().build(
        embedding_build_id=build, embedding_index_id=index,
        embedding_build_batch_id=batch, batch_ordinal=1,
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
    proof = AIEmbeddingSendProof(
        job, build, batch, authorization, trace, actor, "GLOBAL", None, 1,
        provider_route_fingerprint(route), envelope.source_refs_fingerprint,
        envelope.payload_fingerprint, envelope.payload_bytes,
        envelope.input_tokens, now + timedelta(minutes=1),
    )
    value = {
        "id": "request-1", "model": "embed-model", "object": "list",
        "data": [{"index": 0, "embedding": [0.25] * 768}],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }
    body = bytearray(json.dumps(value, separators=(",", ":")).encode())
    response = AIProviderResponse(body, AIProviderResponseObservation(
        hashlib.sha256(body).digest(), len(body), 7, 0, 4, "STOP",
    ))
    parsed = parse_embedding_response(
        response=response, envelope=envelope, route=route,
    )
    response.close()
    claim = RAGIndexBuildClaim(
        job, build, index, "GLOBAL", None, actor, trace, 1, 1, 1,
        now, now + timedelta(minutes=2),
    )
    return envelope, AuthorizedAIEmbeddingSend(route, proof), parsed, claim, now


class _Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class _UOW:
    def __init__(self):
        self.transactions = []

    def __call__(self):
        value = _Transaction()
        self.transactions.append(value)
        return value


class _Claims:
    def __init__(self, value):
        self.value = value

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _Repository:
    def __init__(self, value):
        self.value, self.calls = value, []

    def publish(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.value


class RAGEmbeddingBatchSuccessTests(unittest.TestCase):
    def setUp(self):
        self.envelope, self.send, self.parsed, self.claim, self.now = _facts()
        self.published = PublishedRAGEmbeddingBatch(
            self.envelope.embedding_build_batch_id, (uuid.uuid4(),),
            self.parsed.provider_request_ref, self.now,
        )

    def service(self, *, claim=None, result=True):
        uow = _UOW()
        repository = _Repository(self.published if result is True else result)
        return RAGEmbeddingBatchSuccessService(
            unit_of_work=uow, claims=_Claims(claim or self.claim),
            repository=repository,
        ), uow, repository

    def publish(self, service, *, send=None):
        return service.publish(
            envelope=self.envelope, send=send or self.send,
            parsed=self.parsed, job_id=self.claim.job_id,
            fencing_token=1, worker_ref="rag-worker-a",
        )

    def test_current_claim_publishes_and_commits_exact_record_count(self):
        service, uow, repository = self.service()
        result = self.publish(service)
        self.assertEqual(result, self.published)
        self.assertTrue(uow.transactions[0].committed)
        self.assertEqual(repository.calls[0][1]["parsed"], self.parsed)

    def test_route_payload_claim_or_repository_drift_rolls_back(self):
        changed_route = replace(
            self.send.route, provider_model_key="other-model",
        )
        changed = AuthorizedAIEmbeddingSend(
            changed_route,
            replace(
                self.send.proof,
                route_fingerprint=provider_route_fingerprint(changed_route),
            ),
        )
        cases = (
            (self.service(), changed),
            (self.service(claim=replace(
                self.claim, embedding_index_id=uuid.uuid4())), self.send),
            (self.service(result=None), self.send),
        )
        for (service, uow, _), send in cases:
            with self.subTest(send=send), self.assertRaises(
                    RAGEmbeddingBatchSuccessError):
                self.publish(service, send=send)
            self.assertFalse(any(tx.committed for tx in uow.transactions))

    def test_response_from_another_payload_is_rejected(self):
        service, uow, repository = self.service()
        parsed = replace(
            self.parsed,
            payload_fingerprint=hashlib.sha256(b"other-payload").digest(),
        )
        with self.assertRaises(RAGEmbeddingBatchSuccessError):
            service.publish(
                envelope=self.envelope, send=self.send, parsed=parsed,
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-worker-a",
            )
        self.assertFalse(repository.calls)
        self.assertFalse(any(tx.committed for tx in uow.transactions))


if __name__ == "__main__":
    unittest.main()
