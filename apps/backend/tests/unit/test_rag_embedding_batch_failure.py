from __future__ import annotations

import hashlib
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
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionRoute,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.rag.application.embedding_batch_failure import (
    PublishedRAGEmbeddingBatchFailure,
    RAGEmbeddingBatchFailureError,
    RAGEmbeddingBatchFailurePhase,
    RAGEmbeddingBatchFailureService,
)


def _facts():
    now = datetime(2026, 10, 4, 20, tzinfo=timezone.utc)
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
    claim = RAGIndexBuildClaim(
        job, build, index, "GLOBAL", None, actor, trace, 1, 1, 1,
        now, now + timedelta(minutes=2),
    )
    return envelope, AuthorizedAIEmbeddingSend(route, proof), claim, now


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


class _Jobs:
    def __init__(self):
        self.calls = []

    def retry_or_fail(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return "FAILED"


class _Repository:
    def __init__(self, result):
        self.result, self.calls = result, []

    def publish(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.result


class _Audit:
    def __init__(self):
        self.calls = []

    def append(self, transaction, draft):
        self.calls.append((transaction, draft))
        return uuid.uuid4()


class _Actor:
    def __init__(self, value):
        self.value = value

    def assert_current(self):
        return self.value


class RAGEmbeddingBatchFailureTests(unittest.TestCase):
    def setUp(self):
        self.envelope, self.send, self.claim, self.now = _facts()

    def service(self, *, claim=None, result=None):
        uow, jobs, audit = _UOW(), _Jobs(), _Audit()
        published = result or PublishedRAGEmbeddingBatchFailure(
            self.envelope.embedding_build_batch_id,
            "RAG_EMBEDDING_RESPONSE_INVALID", 1, self.now,
        )
        repository = _Repository(published)
        service = RAGEmbeddingBatchFailureService(
            unit_of_work=uow, claims=_Claims(claim or self.claim), jobs=jobs,
            repository=repository, audit=audit,
            system_actor=_Actor(uuid.uuid4()),
        )
        return service, uow, jobs, repository, audit

    def test_invalid_response_closes_without_retry_and_audits(self):
        service, uow, jobs, repository, audit = self.service()
        fingerprint = hashlib.sha256(b"invalid-response").digest()
        result = service.publish(
            envelope=self.envelope, send=self.send,
            job_id=self.claim.job_id, fencing_token=1,
            worker_ref="rag-worker-a",
            phase=RAGEmbeddingBatchFailurePhase.RESPONSE_INVALID,
            response_fingerprint=fingerprint,
        )
        self.assertEqual(result.error_code, "RAG_EMBEDDING_RESPONSE_INVALID")
        self.assertTrue(uow.transactions[0].committed)
        self.assertFalse(jobs.calls[0][1]["retryable"])
        self.assertEqual(
            repository.calls[0][1]["response_ref"],
            "sha256:" + fingerprint.hex(),
        )
        self.assertEqual(audit.calls[0][1].action, "RAG_INDEX_BUILD_FAILED")

    def test_provider_rejection_has_no_response_reference(self):
        result = PublishedRAGEmbeddingBatchFailure(
            self.envelope.embedding_build_batch_id,
            "RAG_PROVIDER_REQUEST_REJECTED", 0, self.now,
        )
        service, _, _, repository, _ = self.service(result=result)
        published = service.publish(
            envelope=self.envelope, send=self.send,
            job_id=self.claim.job_id, fencing_token=1,
            worker_ref="rag-worker-a",
            phase=RAGEmbeddingBatchFailurePhase.PROVIDER_REJECTED,
        )
        self.assertEqual(published.error_code, "RAG_PROVIDER_REQUEST_REJECTED")
        self.assertIsNone(repository.calls[0][1]["response_ref"])

    def test_bad_fingerprint_or_claim_drift_never_closes_job(self):
        service, uow, jobs, repository, _ = self.service()
        with self.assertRaises(RAGEmbeddingBatchFailureError):
            service.publish(
                envelope=self.envelope, send=self.send,
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-worker-a",
                phase=RAGEmbeddingBatchFailurePhase.RESPONSE_INVALID,
                response_fingerprint=b"bad",
            )
        self.assertFalse(jobs.calls)
        drifted = replace(self.claim, embedding_index_id=uuid.uuid4())
        service, uow, jobs, repository, _ = self.service(claim=drifted)
        with self.assertRaises(RAGEmbeddingBatchFailureError):
            service.publish(
                envelope=self.envelope, send=self.send,
                job_id=self.claim.job_id, fencing_token=1,
                worker_ref="rag-worker-a",
                phase=RAGEmbeddingBatchFailurePhase.PROVIDER_REJECTED,
            )
        self.assertFalse(any(tx.committed for tx in uow.transactions))
        self.assertFalse(jobs.calls)
        self.assertFalse(repository.calls)


if __name__ == "__main__":
    unittest.main()
