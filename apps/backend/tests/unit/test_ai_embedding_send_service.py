from __future__ import annotations

import hashlib
import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingExecutionError,
    AIEmbeddingSendProof,
    AIEmbeddingSource,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AIEmbeddingPreSendError,
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
    AIEmbeddingBatchFenceError,
    AIEmbeddingSendError,
    AIEmbeddingSendService,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError,
)
from plm_assistant.modules.platform.application.trace_context import current_trace_id
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.rag.application.embedding_ai_send_fence import (
    RAGEmbeddingAISendFence,
    RAGEmbeddingAISendFenceError,
)
from plm_assistant.modules.rag.application.embedding_batch_send_fence import (
    FencedRAGEmbeddingBatch,
    RAGEmbeddingBatchSendMaterial,
)


def _facts():
    now = datetime(2026, 10, 4, 16, tzinfo=timezone.utc)
    build_id, index_id, batch_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    text = b"synthetic PLM embedding"
    envelope = AIEmbeddingEnvelopeBuilder().build(
        embedding_build_id=build_id, embedding_index_id=index_id,
        embedding_build_batch_id=batch_id, batch_ordinal=1,
        provider_model_key="text-embedding-v4",
        model_revision="PROVIDER_MANAGED", embedding_dimension=768,
        sources=(AIEmbeddingSource(
            7, uuid.uuid4(), hashlib.sha256(text).digest(), text,
        ),),
    )
    route = AIProviderExecutionRoute(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        ProviderKind.OPENAI_COMPATIBLE, "endpoint.embedding.v1",
        "https://example.test/v1/embeddings", uuid.uuid4(), uuid.uuid4(),
        "text-embedding-v4", "PROVIDER_MANAGED", "cn-beijing",
        "CUSTOMER_CONTENT", 2_000_000, 3, 10, 20,
    )
    proof = AIEmbeddingSendProof(
        uuid.uuid4(), build_id, batch_id, uuid.uuid4(), uuid.uuid4(),
        uuid.uuid4(), "GLOBAL", None, 1, provider_route_fingerprint(route),
        envelope.source_refs_fingerprint, envelope.payload_fingerprint,
        envelope.payload_bytes, envelope.input_tokens,
        now + timedelta(minutes=1),
    )
    return now, envelope, AuthorizedAIEmbeddingSend(route, proof)


def _response():
    body = bytearray(b'{"data":[]}')
    return AIProviderResponse(body, AIProviderResponseObservation(
        hashlib.sha256(body).digest(), len(body), 10, 0, 1, "STOP",
    ))


class _PreSend:
    def __init__(self, events, values):
        self.events, self.values = events, list(values)

    def authorize(self, **kwargs):
        del kwargs
        self.events.append("authorize")
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class _Audit:
    def __init__(self, events, *, fail=False):
        self.events, self.fail = events, fail

    @contextmanager
    def bind(self, envelope, send):
        del envelope, send
        if self.fail:
            raise RuntimeError("private")
        self.events.append("audit-enter")
        try:
            yield
        finally:
            self.events.append("audit-exit")


class _Secrets:
    def __init__(self, events, trace_id, *, fail=False):
        self.events, self.trace_id, self.fail = events, trace_id, fail
        self.buffer = bytearray(b"synthetic-key")

    @contextmanager
    def use(self, *args, **kwargs):
        del args, kwargs
        self.events.append("secret-enter")
        if self.fail:
            self.buffer[:] = b"\x00" * len(self.buffer)
            raise SecretAccessError("secret unavailable")
        if current_trace_id() != self.trace_id:
            raise AssertionError("trace missing")
        view = memoryview(self.buffer)
        try:
            yield view
        finally:
            view.release()
            self.buffer[:] = b"\x00" * len(self.buffer)
            self.events.append("secret-exit")


class _Fence:
    def __init__(self, events, *, fail=False, committed=False):
        self.events, self.fail, self.committed = events, fail, committed
        self.calls = []

    def fence(self, **kwargs):
        self.events.append("fence")
        self.calls.append(kwargs)
        if self.fail:
            raise AIEmbeddingBatchFenceError(committed=self.committed)
        return object()


class _Adapter:
    def __init__(self, events, *, failure=None, invalid=False):
        self.events, self.failure, self.invalid = events, failure, invalid
        self.calls = []

    def send(self, **kwargs):
        self.events.append("adapter")
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return object() if self.invalid else _response()


class _RAGFenceService:
    def __init__(self, now, send, *, drift=False):
        self.now, self.send, self.drift = now, send, drift
        self.calls = []

    def fence(self, *, proof, job_id, fencing_token, worker_ref):
        self.calls.append((proof, job_id, fencing_token, worker_ref))
        send_proof, route = self.send.proof, self.send.route
        claim = RAGIndexBuildClaim(
            job_id, proof.embedding_build_id, proof.embedding_index_id,
            send_proof.scope, send_proof.project_id, send_proof.actor_id,
            send_proof.trace_id, 1, fencing_token, 1, self.now,
            self.now + timedelta(minutes=2),
        )
        material = RAGEmbeddingBatchSendMaterial(
            uuid.uuid4() if self.drift else send_proof.embedding_build_batch_id,
            send_proof.egress_authorization_ref, route.ai_provider_id,
            route.provider_config_version_id, route.ai_model_id,
            route.secret_ref, route.provider_kind.value,
            route.endpoint_policy_ref, route.data_region, route.egress_class,
            route.provider_model_key, route.model_revision, 768,
            send_proof.valid_until, 1,
        )
        return FencedRAGEmbeddingBatch(proof, claim, material, self.now)


class AIEmbeddingSendServiceTests(unittest.TestCase):
    def setUp(self):
        self.now, self.envelope, self.initial = _facts()
        self.events = []

    def service(self, values, *, secret_fail=False, audit_fail=False,
                fence_fail=False, fence_committed=False,
                adapter_failure=None, invalid=False):
        secrets = _Secrets(
            self.events, str(self.initial.proof.trace_id), fail=secret_fail,
        )
        fence = _Fence(
            self.events, fail=fence_fail, committed=fence_committed,
        )
        adapter = _Adapter(
            self.events, failure=adapter_failure, invalid=invalid,
        )
        service = AIEmbeddingSendService(
            pre_send=_PreSend(self.events, values), secrets=secrets,
            adapter=adapter,
            access_audit_scope=_Audit(self.events, fail=audit_fail),
            send_fence=fence, clock=lambda: self.now,
        )
        return service, secrets, fence, adapter

    def send(self, service):
        return service.send_once(
            envelope=self.envelope, job_id=self.initial.proof.job_id,
            fencing_token=1, worker_ref="rag-worker-a",
        )

    def test_exact_order_fences_before_one_adapter_call(self):
        refreshed = AuthorizedAIEmbeddingSend(
            self.initial.route,
            replace(
                self.initial.proof,
                valid_until=self.initial.proof.valid_until
                + timedelta(seconds=5),
            ),
        )
        service, secrets, fence, adapter = self.service(
            [self.initial, refreshed],
        )
        response = self.send(service)
        self.assertEqual(self.events, [
            "authorize", "audit-enter", "secret-enter", "authorize",
            "fence", "adapter", "secret-exit", "audit-exit",
        ])
        self.assertEqual(len(fence.calls), 1)
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0]["proof"], refreshed.proof)
        self.assertEqual(response.authorization, refreshed)
        self.assertTrue(all(value == 0 for value in secrets.buffer))
        response.close()

    def test_fact_drift_or_second_authorization_failure_never_fences(self):
        changed = AuthorizedAIEmbeddingSend(
            replace(self.initial.route, secret_version_id=uuid.uuid4()),
            self.initial.proof,
        )
        cases = (
            ([self.initial, changed], "AI_EMBEDDING_SEND_FACTS_CHANGED"),
            ([self.initial, AIEmbeddingPreSendError()],
             "AI_EMBEDDING_SEND_NOT_AUTHORIZED"),
        )
        for values, expected in cases:
            self.events.clear()
            service, secrets, fence, adapter = self.service(values)
            with self.subTest(expected=expected), self.assertRaises(
                    AIEmbeddingSendError) as caught:
                self.send(service)
            self.assertEqual(caught.exception.code, expected)
            self.assertEqual(fence.calls, [])
            self.assertEqual(adapter.calls, [])
            self.assertTrue(all(value == 0 for value in secrets.buffer))

    def test_secret_audit_or_fence_failure_never_calls_adapter(self):
        for options, expected in (
            ({"secret_fail": True}, "AI_EMBEDDING_SECRET_UNAVAILABLE"),
            ({"audit_fail": True}, "AI_EMBEDDING_SECRET_UNAVAILABLE"),
            ({"fence_fail": True}, "AI_EMBEDDING_SEND_NOT_AUTHORIZED"),
        ):
            self.events.clear()
            values = [self.initial] if options.get("audit_fail") else [
                self.initial, self.initial,
            ]
            service, _, _, adapter = self.service(values, **options)
            with self.subTest(options=options), self.assertRaises(
                    AIEmbeddingSendError) as caught:
                self.send(service)
            self.assertEqual(caught.exception.code, expected)
            self.assertEqual(adapter.calls, [])

        self.events.clear()
        service, _, fence, adapter = self.service(
            [self.initial, self.initial], fence_fail=True,
            fence_committed=True,
        )
        with self.assertRaises(AIEmbeddingSendError) as caught:
            self.send(service)
        self.assertEqual(
            caught.exception.code, "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN",
        )
        self.assertTrue(caught.exception.provider_outcome_unknown)
        self.assertEqual(len(fence.calls), 1)
        self.assertEqual(adapter.calls, [])

    def test_post_fence_adapter_or_response_failure_is_unknown(self):
        for options in (
            {"adapter_failure": AIEmbeddingExecutionError(
                "AI_PROVIDER_NETWORK_UNAVAILABLE")},
            {"invalid": True},
        ):
            self.events.clear()
            service, secrets, fence, adapter = self.service(
                [self.initial, self.initial], **options,
            )
            with self.subTest(options=options), self.assertRaises(
                    AIEmbeddingSendError) as caught:
                self.send(service)
            self.assertEqual(
                caught.exception.code, "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN",
            )
            self.assertTrue(caught.exception.provider_outcome_unknown)
            self.assertEqual(len(fence.calls), 1)
            self.assertEqual(len(adapter.calls), 1)
            self.assertTrue(all(value == 0 for value in secrets.buffer))

    def test_post_fence_http_rejection_is_known_terminal_failure(self):
        service, secrets, fence, adapter = self.service(
            [self.initial, self.initial],
            adapter_failure=AIProviderExecutionError(
                "AI_PROVIDER_HTTP_REJECTED",
            ),
        )
        with self.assertRaises(AIEmbeddingSendError) as caught:
            self.send(service)
        self.assertEqual(
            caught.exception.code, "AI_EMBEDDING_PROVIDER_REJECTED",
        )
        self.assertFalse(caught.exception.provider_outcome_unknown)
        self.assertEqual(caught.exception.authorized_send, self.initial)
        self.assertEqual(len(fence.calls), 1)
        self.assertEqual(len(adapter.calls), 1)
        self.assertTrue(all(value == 0 for value in secrets.buffer))


class RAGEmbeddingAISendFenceTests(unittest.TestCase):
    def setUp(self):
        self.now, self.envelope, self.send = _facts()

    def test_exact_ai_proof_maps_to_current_rag_fence(self):
        underlying = _RAGFenceService(self.now, self.send)
        result = RAGEmbeddingAISendFence(underlying).fence(
            envelope=self.envelope, send=self.send,
            job_id=self.send.proof.job_id, fencing_token=1,
            worker_ref="rag-worker-a", now=self.now,
        )
        self.assertEqual(
            result.proof.batch_ordinal, self.envelope.batch_ordinal,
        )
        self.assertEqual(
            result.proof.source_first_ordinal,
            self.envelope.source_first_ordinal,
        )
        self.assertEqual(len(underlying.calls), 1)

    def test_committed_route_drift_fails_closed(self):
        underlying = _RAGFenceService(self.now, self.send, drift=True)
        with self.assertRaises(RAGEmbeddingAISendFenceError) as caught:
            RAGEmbeddingAISendFence(underlying).fence(
                envelope=self.envelope, send=self.send,
                job_id=self.send.proof.job_id, fencing_token=1,
                worker_ref="rag-worker-a", now=self.now,
            )
        self.assertTrue(caught.exception.committed)


if __name__ == "__main__":
    unittest.main()
