from __future__ import annotations

import hashlib
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingSendProof,
    AIEmbeddingSource,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.application.send_embedding_request import (
    AIEmbeddingSendError,
    SentAIEmbeddingResponse,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.rag.application.embedding_batch_failure import (
    PublishedRAGEmbeddingBatchFailure,
    RAGEmbeddingBatchFailureError,
    RAGEmbeddingBatchFailurePhase,
)
from plm_assistant.modules.rag.application.embedding_batch_success import (
    PublishedRAGEmbeddingBatch,
    RAGEmbeddingBatchSuccessError,
)
from plm_assistant.modules.rag.application.embedding_batch_worker import (
    RAGEmbeddingBatchOneShotWorker,
)


def _facts():
    now = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)
    job, build, index, batch = (uuid.uuid4() for _ in range(4))
    text = b"synthetic worker"
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
        job, build, batch, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        "GLOBAL", None, 1, provider_route_fingerprint(route),
        envelope.source_refs_fingerprint, envelope.payload_fingerprint,
        envelope.payload_bytes, envelope.input_tokens,
        now + timedelta(minutes=1),
    )
    return envelope, job, AuthorizedAIEmbeddingSend(route, proof), now


def _response(envelope, *, valid=True):
    value = {
        "id": "request-worker-1", "model": "embed-model",
        "object": "list", "data": ([{
            "object": "embedding", "index": 0,
            "embedding": [0.5] * 768,
        }] if valid else []),
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }
    body = bytearray(json.dumps(value, separators=(",", ":")).encode())
    return AIProviderResponse(body, AIProviderResponseObservation(
        hashlib.sha256(body).digest(), len(body), 3, 0, 5, "STOP",
    ))


class _Sender:
    def __init__(self, value):
        self.value, self.calls = value, []

    def send_once(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class _Success:
    def __init__(self, value):
        self.value, self.calls = value, []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class _Failure:
    def __init__(self, value):
        self.value, self.calls = value, []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class RAGEmbeddingBatchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.envelope, self.job, self.send, self.now = _facts()
        self.record_id = uuid.uuid4()

    def worker(self, sender_value, *, success_value=None,
               failure_value=None):
        sender = _Sender(sender_value)
        success = _Success(success_value or PublishedRAGEmbeddingBatch(
            self.envelope.embedding_build_batch_id, (self.record_id,),
            "request-worker-1", self.now,
        ))
        failure = _Failure(failure_value or PublishedRAGEmbeddingBatchFailure(
            self.envelope.embedding_build_batch_id,
            "RAG_EMBEDDING_RESPONSE_INVALID", 0, self.now,
        ))
        return (
            RAGEmbeddingBatchOneShotWorker(
                sender=sender, success=success, failure=failure,
            ), sender, success, failure,
        )

    def run_worker(self, worker):
        return worker.run_once(
            envelope=self.envelope, job_id=self.job,
            fencing_token=1, worker_ref="rag-worker-a",
        )

    def test_valid_response_publishes_exact_final_authorization(self):
        raw = _response(self.envelope)
        sent = SentAIEmbeddingResponse(raw, self.send)
        worker, _, success, failure = self.worker(sent)
        result = self.run_worker(worker)
        self.assertEqual(result.state, "BATCH_SUCCEEDED")
        self.assertEqual(result.embedding_record_ids, (self.record_id,))
        self.assertEqual(success.calls[0]["send"], self.send)
        self.assertFalse(failure.calls)
        with self.assertRaises(AIProviderExecutionError):
            raw.view()

    def test_known_provider_rejection_closes_build(self):
        error = AIEmbeddingSendError(
            "AI_EMBEDDING_PROVIDER_REJECTED", authorized_send=self.send,
        )
        failure_value = PublishedRAGEmbeddingBatchFailure(
            self.envelope.embedding_build_batch_id,
            "RAG_PROVIDER_REQUEST_REJECTED", 1, self.now,
        )
        worker, _, success, failure = self.worker(
            error, failure_value=failure_value,
        )
        result = self.run_worker(worker)
        self.assertEqual(result.state, "BUILD_FAILED")
        self.assertEqual(result.error_code, "RAG_PROVIDER_REQUEST_REJECTED")
        self.assertIs(
            failure.calls[0]["phase"],
            RAGEmbeddingBatchFailurePhase.PROVIDER_REJECTED,
        )
        self.assertFalse(success.calls)

    def test_unknown_send_is_never_replayed_or_terminalized_as_known(self):
        worker, sender, success, failure = self.worker(AIEmbeddingSendError(
            "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN",
            provider_outcome_unknown=True,
        ))
        result = self.run_worker(worker)
        self.assertEqual(result.state, "RECONCILIATION_PENDING")
        self.assertEqual(result.error_code, "RAG_PROVIDER_OUTCOME_UNKNOWN")
        self.assertEqual(len(sender.calls), 1)
        self.assertFalse(success.calls)
        self.assertFalse(failure.calls)

    def test_invalid_response_closes_build_with_response_fingerprint(self):
        raw = _response(self.envelope, valid=False)
        fingerprint = raw.observation.response_fingerprint
        worker, _, success, failure = self.worker(
            SentAIEmbeddingResponse(raw, self.send),
        )
        result = self.run_worker(worker)
        self.assertEqual(result.state, "BUILD_FAILED")
        self.assertEqual(
            failure.calls[0]["response_fingerprint"], fingerprint,
        )
        self.assertIs(
            failure.calls[0]["phase"],
            RAGEmbeddingBatchFailurePhase.RESPONSE_INVALID,
        )
        self.assertFalse(success.calls)
        with self.assertRaises(AIProviderExecutionError):
            raw.view()

    def test_publication_failure_requires_reconciliation_without_resend(self):
        raw = _response(self.envelope)
        worker, sender, success, failure = self.worker(
            SentAIEmbeddingResponse(raw, self.send),
            success_value=RAGEmbeddingBatchSuccessError(
                "RAG_EMBEDDING_RESULT_NOT_PUBLISHED",
            ),
        )
        result = self.run_worker(worker)
        self.assertEqual(result.state, "RECONCILIATION_PENDING")
        self.assertEqual(
            result.error_code, "RAG_EMBEDDING_RESULT_NOT_PUBLISHED",
        )
        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(len(success.calls), 1)
        self.assertFalse(failure.calls)

    def test_failure_publication_failure_stays_pending(self):
        error = AIEmbeddingSendError(
            "AI_EMBEDDING_PROVIDER_REJECTED", authorized_send=self.send,
        )
        worker, _, _, failure = self.worker(
            error,
            failure_value=RAGEmbeddingBatchFailureError(
                "RAG_EMBEDDING_FAILURE_NOT_PUBLISHED",
            ),
        )
        result = self.run_worker(worker)
        self.assertEqual(result.state, "RECONCILIATION_PENDING")
        self.assertEqual(
            result.error_code, "RAG_EMBEDDING_FAILURE_NOT_PUBLISHED",
        )
        self.assertEqual(len(failure.calls), 1)


if __name__ == "__main__":
    unittest.main()
