"""Windows 11/PostgreSQL 18 proof for one-shot Embedding batch Worker."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.application.send_embedding_request import (
    AIEmbeddingSendError,
    SentAIEmbeddingResponse,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.rag.application.embedding_batch_failure import (
    RAGEmbeddingBatchFailureService,
)
from plm_assistant.modules.rag.application.embedding_batch_success import (
    RAGEmbeddingBatchSuccessService,
)
from plm_assistant.modules.rag.application.embedding_batch_worker import (
    RAGEmbeddingBatchOneShotWorker,
)
from plm_assistant.modules.rag.infrastructure.embedding_batch_failure_repository import (
    SqlAlchemyRAGEmbeddingBatchFailureRepository,
)
from plm_assistant.modules.rag.infrastructure.embedding_batch_success_repository import (
    SqlAlchemyRAGEmbeddingBatchSuccessRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/rag-03-a04-p04-embedding-send-boundary/verify.py",
    "rag_embedding_batch_worker_fixture",
)


class _SystemActor:
    def __init__(self, value):
        self.value = value

    def assert_current(self):
        return self.value


def _worker(context, sender):
    return RAGEmbeddingBatchOneShotWorker(
        sender=sender,
        success=RAGEmbeddingBatchSuccessService(
            unit_of_work=context["runtime"].unit_of_work,
            claims=context["claims"],
            repository=SqlAlchemyRAGEmbeddingBatchSuccessRepository(),
        ),
        failure=RAGEmbeddingBatchFailureService(
            unit_of_work=context["runtime"].unit_of_work,
            claims=context["claims"], jobs=SqlAlchemyJobLeaseRepository(),
            repository=SqlAlchemyRAGEmbeddingBatchFailureRepository(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            system_actor=_SystemActor(context["actor"]),
        ),
    )


def _run(context, envelope, sender):
    return _worker(context, sender).run_once(
        envelope=envelope, job_id=context["claim"].job_id,
        fencing_token=context["claim"].fencing_token,
        worker_ref="rag-worker-01",
    )


def execute_success(context, envelope, service, adapter) -> None:
    result = _run(context, envelope, service)
    assert result.state == "BATCH_SUCCEEDED"
    assert len(result.embedding_record_ids) == envelope.record_count
    assert len(adapter.calls) == 1
    with fixture.fixture.connect(context["database"]) as db:
        state = db.execute(
            "SELECT batch_state,provider_request_ref,lock_version FROM "
            "plm.rag_embedding_build_batches WHERE "
            "embedding_build_batch_id=%s",
            (envelope.embedding_build_batch_id,),
        ).fetchone()
        records = db.execute(
            "SELECT count(*) FROM plm.rag_embedding_records WHERE "
            "embedding_index_id=%s",
            (envelope.embedding_index_id,),
        ).fetchone()[0]
    assert state == ("SUCCEEDED", "synthetic-request-1", 2)
    assert records == envelope.record_count
    print(
        "RAG_03_A04_P06_WORKER_SUCCESS_PASS: one-shot Worker used the exact "
        "second authorization, parsed one synthetic response and atomically "
        "published the float32 EmbeddingRecord set"
    )


class _InvalidAfterSend:
    def __init__(self, underlying):
        self.underlying = underlying

    def send_once(self, **kwargs):
        envelope = kwargs["envelope"]
        with self.underlying.send_once(**kwargs) as sent:
            authorization = sent.authorization
        body = bytearray(json.dumps({
            "id": "synthetic-invalid-1", "object": "list",
            "model": envelope.provider_model_key, "data": [],
            "usage": {
                "prompt_tokens": envelope.input_tokens,
                "total_tokens": envelope.input_tokens,
            },
        }, separators=(",", ":")).encode())
        response = AIProviderResponse(body, AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body),
            envelope.input_tokens, 0, 1, "STOP",
        ))
        return SentAIEmbeddingResponse(response, authorization)


def execute_invalid(context, envelope, service, adapter) -> None:
    result = _run(context, envelope, _InvalidAfterSend(service))
    assert result.state == "BUILD_FAILED"
    assert result.error_code == "RAG_EMBEDDING_RESPONSE_INVALID"
    assert len(adapter.calls) == 1
    with fixture.fixture.connect(context["database"]) as db:
        state = db.execute(
            "SELECT batch_state,error_code,provider_request_ref LIKE "
            "'sha256:%%' FROM plm.rag_embedding_build_batches WHERE "
            "embedding_build_batch_id=%s",
            (envelope.embedding_build_batch_id,),
        ).fetchone()
        records = db.execute(
            "SELECT count(*) FROM plm.rag_embedding_records WHERE "
            "embedding_index_id=%s",
            (envelope.embedding_index_id,),
        ).fetchone()[0]
    assert state == ("FAILED", "RAG_EMBEDDING_RESPONSE_INVALID", True)
    assert records == 0
    print(
        "RAG_03_A04_P06_WORKER_INVALID_PASS: one-shot Worker retained the "
        "invalid response fingerprint and atomically failed the Build without "
        "vectors or retry"
    )


class _UnknownAfterSend:
    def __init__(self, underlying):
        self.underlying = underlying

    def send_once(self, **kwargs):
        sent = self.underlying.send_once(**kwargs)
        sent.close()
        raise AIEmbeddingSendError(
            "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN",
            provider_outcome_unknown=True,
        )


def execute_unknown(context, envelope, service, adapter) -> None:
    result = _run(context, envelope, _UnknownAfterSend(service))
    assert result.state == "RECONCILIATION_PENDING"
    assert result.error_code == "RAG_PROVIDER_OUTCOME_UNKNOWN"
    assert len(adapter.calls) == 1
    with fixture.fixture.connect(context["database"]) as db:
        state = db.execute(
            "SELECT batch_state,lock_version FROM "
            "plm.rag_embedding_build_batches WHERE "
            "embedding_build_batch_id=%s",
            (envelope.embedding_build_batch_id,),
        ).fetchone()
        job = db.execute(
            "SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s",
            (context["claim"].job_id,),
        ).fetchone()
        records = db.execute(
            "SELECT count(*) FROM plm.rag_embedding_records WHERE "
            "embedding_index_id=%s",
            (envelope.embedding_index_id,),
        ).fetchone()[0]
    assert state == ("RUNNING", 1)
    assert job == ("RUNNING", 1)
    assert records == 0
    print(
        "RAG_03_A04_P06_WORKER_UNKNOWN_PASS: one-shot Worker performed one "
        "synthetic send, made no replay or false terminal claim, and left the "
        "durable RUNNING fence for the verified expiry reconciler"
    )


def main() -> None:
    fixture.main(execute=execute_success)
    fixture.main(execute=execute_invalid)
    fixture.main(execute=execute_unknown)
    print(
        "RAG_03_A04_P06_BATCH_WORKER_PASS: Windows 11/PostgreSQL18.6 "
        "success, invalid-response and unknown-outcome Worker branches passed; "
        "zero real Provider I/O"
    )


if __name__ == "__main__":
    main()
