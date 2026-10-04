"""Windows 11/PostgreSQL 18 proof for the complete Embedding send boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from datetime import timedelta
from pathlib import Path

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelopeBuilder,
    AIEmbeddingSource,
    require_embedding_send,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AIEmbeddingPreSendService,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy,
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.application.send_embedding_request import (
    AIEmbeddingSendService,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.embedding_provider_secret_audit import (
    AIEmbeddingProviderSecretAccessAudit,
)
from plm_assistant.modules.ai.infrastructure.embedding_route_repository import (
    SqlAlchemyAIEmbeddingRouteRepository,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer,
    SecretEnvelope,
    SecretPurpose,
    SecretRef,
    SecretResolver,
    SecretState,
)
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import (
    SqlAlchemyAIProviderSecretProof,
)
from plm_assistant.modules.rag.application.embedding_ai_send_fence import (
    RAGEmbeddingAISendFence,
)
from plm_assistant.modules.rag.application.embedding_batch_send_fence import (
    RAGEmbeddingBatchSendFenceService,
)
from plm_assistant.modules.rag.infrastructure.embedding_batch_send_fence_repository import (
    SqlAlchemyRAGEmbeddingBatchSendFenceRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/rag-03-a03-p02-build-begin/verify.py",
    "rag_embedding_send_boundary_fixture",
)


class _License:
    def __init__(self):
        self.calls = []

    def require_valid(self, *, trace_id):
        self.calls.append(trace_id)
        return object()


class _SystemActor:
    def __init__(self, value):
        self.value = value

    def assert_current(self):
        return self.value


class _Store:
    def __init__(self, envelope):
        self.envelope = envelope

    def load(self, secret_ref):
        return self.envelope if secret_ref == self.envelope.secret_ref else None


class _Decryptor:
    def __init__(self):
        self.plaintext = None

    def decrypt(self, envelope):
        del envelope
        self.plaintext = bytearray(b"synthetic-key-never-sent")
        return self.plaintext


class _Adapter:
    def __init__(self):
        self.calls = []

    def send(self, *, route, proof, envelope, key):
        require_embedding_send(
            proof, route, envelope,
            now=proof.valid_until - timedelta(microseconds=1),
        )
        assert bytes(key) == b"synthetic-key-never-sent"
        self.calls.append((route, proof, envelope))
        body = bytearray(b'{"data":[],"synthetic":true}')
        return AIProviderResponse(body, AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body),
            envelope.input_tokens, 0, envelope.input_tokens, "STOP",
        ))


def validate(context: dict[str, object]) -> None:
    database = context["database"]
    planned = context["planned"]
    claim = context["claim"]
    first = context["batches"][0]
    member = context["members"][0]
    actor = context["actor"]
    runtime = context["runtime"]
    with fixture.connect(database) as db:
        row = db.execute(
            "SELECT batch.embedding_build_batch_id,build.embedding_model_ref,"
            "model.provider_model_key,model.model_revision,model.embedding_dimension,"
            "config.secret_ref FROM plm.rag_embedding_build_batches batch "
            "JOIN plm.rag_embedding_builds build ON build.embedding_build_id="
            "batch.embedding_build_id JOIN plm.ai_models model ON "
            "model.ai_model_id=build.embedding_model_ref JOIN "
            "plm.ai_provider_config_versions config ON config.ai_provider_id="
            "model.ai_provider_id WHERE batch.embedding_build_id=%s "
            "AND batch.batch_ordinal=1",
            (planned.embedding_build_id,),
        ).fetchone()
        batch_id, _, model_key, revision, dimension, secret_ref = row
    body = b"PLM begin one"
    envelope = AIEmbeddingEnvelopeBuilder().build(
        embedding_build_id=planned.embedding_build_id,
        embedding_index_id=planned.embedding_index_id,
        embedding_build_batch_id=batch_id, batch_ordinal=1,
        provider_model_key=model_key, model_revision=revision,
        embedding_dimension=dimension,
        sources=(AIEmbeddingSource(member[0], member[1], member[2], body),),
    )
    assert envelope.source_refs_fingerprint == first.source_batch_fingerprint
    assert envelope.payload_fingerprint == first.payload_fingerprint
    assert envelope.payload_bytes == first.payload_bytes
    assert envelope.input_tokens == first.input_tokens
    secret_version = uuid.uuid4()
    with fixture.connect(database) as db:
        with db.transaction():
            db.execute(
                "INSERT INTO plm.plt_secret_versions(secret_version_id,"
                "secret_record_id,version_no,encrypted_payload,encryption_metadata,"
                "key_provider_ref,created_by,activated_at) VALUES "
                "(%s,%s,1,%s,'{}'::jsonb,'synthetic-validation',%s,"
                "statement_timestamp())",
                (secret_version, secret_ref, b"synthetic-ciphertext", actor),
            )
            db.execute(
                "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',"
                "current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s",
                (secret_version, secret_ref),
            )

    guard = _License()
    pre_send = AIEmbeddingPreSendService(
        unit_of_work=runtime.unit_of_work, claims=context["claims"],
        repository=SqlAlchemyAIEmbeddingRouteRepository(),
        secret_proof=SqlAlchemyAIProviderSecretProof(),
        policies=AIProviderExecutionPolicyRegistry((AIProviderExecutionPolicy(
            "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
            "https://example.test/v1/embeddings", "cn-beijing",
            "EXTERNAL_APPROVAL_REQUIRED", frozenset({model_key}),
            2_000_000, 3, 10, 20,
        ),)),
        license_guard=guard,
    )
    audit = AIEmbeddingProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=_SystemActor(actor),
    )
    secret = SecretEnvelope(
        SecretRef(secret_ref), SecretPurpose.AI_PROVIDER_KEY,
        SecretState.ACTIVE, SecretConsumer.AI_PROVIDER_ADAPTER, 1,
        b"synthetic-ciphertext", b"{}", "synthetic-validation",
        secret_version,
    )
    decryptor = _Decryptor()
    adapter = _Adapter()
    service = AIEmbeddingSendService(
        pre_send=pre_send,
        secrets=SecretResolver(_Store(secret), decryptor, audit),
        adapter=adapter, access_audit_scope=audit,
        send_fence=RAGEmbeddingAISendFence(RAGEmbeddingBatchSendFenceService(
            unit_of_work=runtime.unit_of_work, claims=context["claims"],
            repository=SqlAlchemyRAGEmbeddingBatchSendFenceRepository(),
        )),
    )
    with service.send_once(
        envelope=envelope, job_id=claim.job_id,
        fencing_token=claim.fencing_token, worker_ref="rag-worker-01",
    ) as response:
        assert b"synthetic" in bytes(response.view())
    assert len(adapter.calls) == 1
    assert len(guard.calls) == 4
    assert decryptor.plaintext is not None
    assert all(value == 0 for value in decryptor.plaintext)
    with fixture.connect(database) as db:
        state = db.execute(
            "SELECT batch_state,send_fencing_token,lock_version FROM "
            "plm.rag_embedding_build_batches WHERE embedding_build_batch_id=%s",
            (batch_id,),
        ).fetchone()
        events = db.execute(
            "SELECT action,outcome,after_state FROM plm.aud_events "
            "WHERE trace_id=%s AND action='AI_PROVIDER_SECRET_ACCESS'",
            (claim.trace_id,),
        ).fetchall()
    assert state == ("RUNNING", 1, 1)
    assert events == [("AI_PROVIDER_SECRET_ACCESS", "SUCCESS", "RAG_EMBEDDING_SEND")]
    print(
        "RAG_03_A04_P04_EMBEDDING_SEND_BOUNDARY_PASS: Windows 11/"
        "PostgreSQL18.6 re-authorized current route and Secret version twice, "
        "persisted one scoped Secret audit, atomically fenced one exact Batch, "
        "called one synthetic Adapter, zeroed plaintext, and performed zero "
        "real Provider I/O"
    )


def main() -> None:
    bodies = {1: b"PLM begin one", 2: b"PLM begin two"}

    def payload_factory(ordinal, member):
        envelope = AIEmbeddingEnvelopeBuilder().build(
            embedding_build_id=uuid.uuid4(),
            embedding_index_id=uuid.uuid4(),
            embedding_build_batch_id=uuid.uuid4(), batch_ordinal=ordinal,
            provider_model_key="embed-rag-1024", model_revision="rev-1",
            embedding_dimension=1024,
            sources=(AIEmbeddingSource(
                member[0], member[1], member[2], bodies[ordinal],
            ),),
        )
        return (
            envelope.payload_fingerprint, envelope.payload_bytes,
            envelope.input_tokens,
        )

    fixture.main(
        after_begin=validate, batch_payload_factory=payload_factory,
    )


if __name__ == "__main__":
    main()
