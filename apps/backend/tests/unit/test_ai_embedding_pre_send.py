from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingSource,
    require_embedding_send,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AIEmbeddingPreSendError,
    AIEmbeddingPreSendService,
    AIEmbeddingRouteMaterial,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy,
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
    RAGIndexBuildClaims,
)
from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _ClaimRepository:
    def __init__(self, value):
        self.value = value

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _RouteRepository:
    def __init__(self, value):
        self.value = value

    def load_current(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _Secrets:
    def __init__(self, value):
        self.value = value

    def active_provider_key_version(self, transaction, **kwargs):
        del transaction, kwargs
        return self.value


class _Guard:
    def __init__(self, fail_on=0):
        self.calls = 0
        self.fail_on = fail_on

    def require_valid(self, **kwargs):
        del kwargs
        self.calls += 1
        if self.calls == self.fail_on:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class AIEmbeddingPreSendTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, 15, tzinfo=timezone.utc)
        self.job_id, self.build_id, self.index_id, self.batch_id = (
            uuid.uuid4() for _ in range(4)
        )
        self.actor_id, self.trace_id = uuid.uuid4(), uuid.uuid4()
        self.provider_id, self.config_id, self.model_id = (
            uuid.uuid4() for _ in range(3)
        )
        self.secret_ref, self.secret_version, self.authorization_id = (
            uuid.uuid4() for _ in range(3)
        )
        sources = tuple(
            AIEmbeddingSource(
                ordinal, uuid.uuid4(), hashlib.sha256(text).digest(), text,
            )
            for ordinal, text in enumerate((b"PLM-1", b"PLM-2"), 11)
        )
        self.envelope = AIEmbeddingEnvelopeBuilder().build(
            embedding_build_id=self.build_id,
            embedding_index_id=self.index_id,
            embedding_build_batch_id=self.batch_id,
            batch_ordinal=2,
            provider_model_key="text-embedding-v4",
            model_revision="PROVIDER_MANAGED",
            embedding_dimension=1024,
            sources=sources,
        )
        self.claim = RAGIndexBuildClaim(
            self.job_id, self.build_id, self.index_id, "GLOBAL", None,
            self.actor_id, self.trace_id, 1, 1, 1, self.now,
            self.now + timedelta(minutes=2),
        )
        self.material = AIEmbeddingRouteMaterial(
            self.job_id, self.build_id, self.batch_id, self.index_id,
            self.authorization_id, self.envelope.source_refs_fingerprint,
            self.envelope.payload_fingerprint, self.envelope.payload_bytes,
            self.envelope.input_tokens, self.envelope.record_count,
            self.provider_id, self.config_id, self.model_id,
            ProviderKind.OPENAI_COMPATIBLE, "BAILIAN_EMBEDDING_V1",
            self.secret_ref, "cn-beijing", "CUSTOMER_CONTENT",
            "text-embedding-v4", "PROVIDER_MANAGED", 1024,
            self.now + timedelta(minutes=10),
        )
        self.policy = AIProviderExecutionPolicy(
            "BAILIAN_EMBEDDING_V1", ProviderKind.OPENAI_COMPATIBLE,
            "https://example.test/v1/embeddings", "cn-beijing",
            "CUSTOMER_CONTENT", frozenset({"text-embedding-v4"}),
            10_000_000, 3, 20, 30,
        )

    def service(self, *, claim=None, material=None, secret_version=True,
                policy=None, guard=None):
        guard = guard or _Guard()
        claims = RAGIndexBuildClaims(
            unit_of_work=_Transaction,
            repository=_ClaimRepository(self.claim if claim is None else claim),
        )
        service = AIEmbeddingPreSendService(
            unit_of_work=_Transaction,
            claims=claims,
            repository=_RouteRepository(
                self.material if material is None else material,
            ),
            secret_proof=_Secrets(
                self.secret_version if secret_version is True else secret_version,
            ),
            policies=AIProviderExecutionPolicyRegistry((policy or self.policy,)),
            license_guard=guard,
        )
        return service, guard

    def authorize(self, service):
        return service.authorize(
            envelope=self.envelope, job_id=self.job_id, fencing_token=1,
            worker_ref="rag-worker-a", now=self.now,
        )

    def test_current_facts_authorize_one_bounded_embedding_route(self):
        service, guard = self.service()
        result = self.authorize(service)
        self.assertEqual(result.route.secret_version_id, self.secret_version)
        self.assertEqual(result.proof.embedding_build_batch_id, self.batch_id)
        self.assertEqual(
            result.proof.valid_until,
            self.claim.lease_expires_at - timedelta(seconds=32),
        )
        self.assertIs(require_embedding_send(
            result.proof, result.route, self.envelope, now=self.now,
        ), result.proof)
        self.assertEqual(guard.calls, 2)

    def test_route_payload_secret_and_identity_drift_fail_closed(self):
        cases = (
            self.service(material=replace(
                self.material, provider_model_key="other-model",
            )),
            self.service(material=replace(
                self.material, payload_fingerprint=b"x" * 32,
            )),
            self.service(material=replace(
                self.material, embedding_index_id=uuid.uuid4(),
            )),
            self.service(secret_version=None),
        )
        for service, _ in cases:
            with self.subTest(service=service), self.assertRaises(
                    AIEmbeddingPreSendError):
                self.authorize(service)

    def test_policy_or_lease_window_drift_fails_closed(self):
        policy = replace(
            self.policy, allowed_model_keys=frozenset({"other-model"}),
        )
        short_claim = replace(
            self.claim, lease_expires_at=self.now + timedelta(seconds=32),
        )
        for service, _ in (
                self.service(policy=policy), self.service(claim=short_claim)):
            with self.subTest(service=service), self.assertRaises(
                    AIEmbeddingPreSendError):
                self.authorize(service)

    def test_license_is_checked_inside_and_after_transaction(self):
        for failure in (1, 2):
            guard = _Guard(fail_on=failure)
            service, _ = self.service(guard=guard)
            with self.subTest(failure=failure), self.assertRaises(
                    AIEmbeddingPreSendError):
                self.authorize(service)
            self.assertEqual(guard.calls, failure)


if __name__ == "__main__":
    unittest.main()
