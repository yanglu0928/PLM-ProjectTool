from __future__ import annotations

import hashlib
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
    AIProviderExecutionRoute,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.embedding_provider_secret_audit import (
    AIEmbeddingProviderSecretAccessAudit,
    AIEmbeddingSecretAuditError,
)
from plm_assistant.modules.platform.application.secret_access import SecretRef
from plm_assistant.modules.platform.application.trace_context import trace_scope


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
        self.values = []

    def __call__(self):
        value = _Transaction()
        self.values.append(value)
        return value


class _Audit:
    def __init__(self):
        self.drafts = []

    def append(self, transaction, draft):
        del transaction
        self.drafts.append(draft)
        return uuid.uuid4()


class _Actor:
    def __init__(self):
        self.value = uuid.uuid4()

    def assert_current(self):
        return self.value


def _facts(scope="GLOBAL"):
    now = datetime(2026, 10, 4, 16, tzinfo=timezone.utc)
    project_id = uuid.uuid4() if scope == "PROJECT" else None
    build_id, index_id, batch_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    text = b"synthetic"
    envelope = AIEmbeddingEnvelopeBuilder().build(
        embedding_build_id=build_id, embedding_index_id=index_id,
        embedding_build_batch_id=batch_id, batch_ordinal=1,
        provider_model_key="text-embedding-v4",
        model_revision="PROVIDER_MANAGED", embedding_dimension=768,
        sources=(AIEmbeddingSource(
            1, uuid.uuid4(), hashlib.sha256(text).digest(), text,
        ),),
    )
    route = AIProviderExecutionRoute(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        ProviderKind.OPENAI_COMPATIBLE, "endpoint.embedding.v1",
        "https://example.test/v1/embeddings", uuid.uuid4(), uuid.uuid4(),
        "text-embedding-v4", "PROVIDER_MANAGED", "cn-beijing",
        "CUSTOMER_CONTENT", 100000, 3, 10, 20,
    )
    proof = AIEmbeddingSendProof(
        uuid.uuid4(), build_id, batch_id, uuid.uuid4(), uuid.uuid4(),
        uuid.uuid4(), scope, project_id, 1, provider_route_fingerprint(route),
        envelope.source_refs_fingerprint, envelope.payload_fingerprint,
        envelope.payload_bytes, envelope.input_tokens,
        now + timedelta(minutes=1),
    )
    return envelope, AuthorizedAIEmbeddingSend(route, proof)


class AIEmbeddingSecretAuditTests(unittest.TestCase):
    def service(self):
        uow, audit, actor = _UOW(), _Audit(), _Actor()
        return AIEmbeddingProviderSecretAccessAudit(
            unit_of_work=uow, audit=audit, system_actor=actor,
        ), uow, audit

    def test_global_and_project_access_are_append_only_and_scoped(self):
        for scope, expected_scope in (
                ("GLOBAL", "DEPLOYMENT"), ("PROJECT", "PROJECT")):
            service, uow, audit = self.service()
            envelope, send = _facts(scope)
            with service.bind(envelope, send), trace_scope(
                    str(send.proof.trace_id)):
                service.record_access(
                    secret_ref=SecretRef(send.route.secret_ref),
                    consumer="AI_PROVIDER_ADAPTER", outcome="GRANTED",
                    trace_id=str(send.proof.trace_id),
                )
            self.assertEqual(audit.drafts[0].event_scope, expected_scope)
            self.assertEqual(
                audit.drafts[0].target_project_id, send.proof.project_id,
            )
            self.assertEqual(
                audit.drafts[0].after_state, "RAG_EMBEDDING_SEND",
            )
            self.assertTrue(uow.values[0].committed)

    def test_unbound_or_wrong_secret_access_is_denied(self):
        service, _, _ = self.service()
        envelope, send = _facts()
        with self.assertRaises(AIEmbeddingSecretAuditError):
            service.record_access(
                secret_ref=SecretRef(send.route.secret_ref),
                consumer="AI_PROVIDER_ADAPTER", outcome="GRANTED",
                trace_id=str(send.proof.trace_id),
            )
        with service.bind(envelope, send), self.assertRaises(
                AIEmbeddingSecretAuditError):
            service.record_access(
                secret_ref=SecretRef(uuid.uuid4()),
                consumer="AI_PROVIDER_ADAPTER", outcome="GRANTED",
                trace_id=str(send.proof.trace_id),
            )


if __name__ == "__main__":
    unittest.main()
