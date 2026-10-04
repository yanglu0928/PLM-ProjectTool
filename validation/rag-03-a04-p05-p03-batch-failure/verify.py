"""Windows 11/PostgreSQL 18 proof for known Embedding failure closure."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command

from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.rag.application.embedding_batch_failure import (
    RAGEmbeddingBatchFailurePhase,
    RAGEmbeddingBatchFailureService,
)
from plm_assistant.modules.rag.infrastructure.embedding_batch_failure_repository import (
    SqlAlchemyRAGEmbeddingBatchFailureRepository,
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
    "rag_embedding_batch_failure_fixture",
)


class _SystemActor:
    def __init__(self, value):
        self.value = value

    def assert_current(self):
        return self.value


def publish_failure(context, envelope, route, proof, response) -> None:
    service = RAGEmbeddingBatchFailureService(
        unit_of_work=context["runtime"].unit_of_work,
        claims=context["claims"], jobs=SqlAlchemyJobLeaseRepository(),
        repository=SqlAlchemyRAGEmbeddingBatchFailureRepository(),
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=_SystemActor(context["actor"]),
    )
    result = service.publish(
        envelope=envelope, send=AuthorizedAIEmbeddingSend(route, proof),
        job_id=context["claim"].job_id,
        fencing_token=context["claim"].fencing_token,
        worker_ref="rag-worker-01",
        phase=RAGEmbeddingBatchFailurePhase.RESPONSE_INVALID,
        response_fingerprint=response.observation.response_fingerprint,
    )
    assert result.cancelled_batch_count == 1
    response_ref = "sha256:" + response.observation.response_fingerprint.hex()
    with fixture.fixture.connect(context["database"]) as db:
        batches = db.execute(
            "SELECT batch_ordinal,batch_state,provider_request_ref,error_code,"
            "lock_version FROM plm.rag_embedding_build_batches WHERE "
            "embedding_build_id=%s ORDER BY batch_ordinal",
            (context["planned"].embedding_build_id,),
        ).fetchall()
        aggregate = db.execute(
            "SELECT build.build_state,build.lock_version,idx.index_state,"
            "idx.lock_version,job.state,job.completed_at IS NOT NULL,"
            "job.lease_expires_at IS NULL,lease.state,attempt.error_code,"
            "attempt.completed_at=job.completed_at FROM plm.rag_embedding_builds build "
            "JOIN plm.rag_embedding_indexes idx ON idx.embedding_index_id="
            "build.embedding_index_id JOIN plm.job_jobs job ON job.job_id="
            "build.build_job_ref JOIN plm.job_leases lease ON lease.job_id="
            "job.job_id AND lease.fencing_token=1 JOIN plm.job_attempts attempt "
            "ON attempt.job_id=job.job_id AND attempt.fencing_token=1 WHERE "
            "build.embedding_build_id=%s",
            (context["planned"].embedding_build_id,),
        ).fetchone()
        records = db.execute(
            "SELECT count(*) FROM plm.rag_embedding_records WHERE "
            "embedding_index_id=%s",
            (context["planned"].embedding_index_id,),
        ).fetchone()[0]
        audit = db.execute(
            "SELECT action,outcome,reason_code,before_state,after_state "
            "FROM plm.aud_events WHERE trace_id=%s AND "
            "action='RAG_INDEX_BUILD_FAILED'",
            (context["claim"].trace_id,),
        ).fetchall()
    assert batches == [
        (1, "FAILED", response_ref,
         "RAG_EMBEDDING_RESPONSE_INVALID", 2),
        (2, "CANCELLED", None,
         "RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE", 1),
    ]
    assert aggregate == (
        "FAILED", 2, "FAILED", 2, "FAILED", True, True,
        "RELEASED", "RAG_EMBEDDING_RESPONSE_INVALID", True,
    )
    assert records == 0
    assert audit == [(
        "RAG_INDEX_BUILD_FAILED", "FAILED",
        "RAG_EMBEDDING_RESPONSE_INVALID", "RUNNING", "FAILED",
    )]
    try:
        command.downgrade(context["config"], "20261004_0083")
    except Exception as error:
        assert "known RAG Embedding failure history prevents downgrade" in str(error)
    else:
        raise AssertionError("known Embedding failure history was downgraded")
    print(
        "RAG_03_A04_P05_P03_BATCH_FAILURE_PASS: Windows 11/PostgreSQL18.6 "
        "atomically failed one fenced Batch, cancelled one unsent Batch, "
        "closed Job/Lease/Attempt/Build/Index, retained the invalid response "
        "fingerprint and Audit, wrote zero vectors, and allowed no retry or "
        "real Provider I/O"
    )


def publish_provider_rejection(context, envelope, route, proof, response) -> None:
    result = RAGEmbeddingBatchFailureService(
        unit_of_work=context["runtime"].unit_of_work,
        claims=context["claims"], jobs=SqlAlchemyJobLeaseRepository(),
        repository=SqlAlchemyRAGEmbeddingBatchFailureRepository(),
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=_SystemActor(context["actor"]),
    ).publish(
        envelope=envelope, send=AuthorizedAIEmbeddingSend(route, proof),
        job_id=context["claim"].job_id,
        fencing_token=context["claim"].fencing_token,
        worker_ref="rag-worker-01",
        phase=RAGEmbeddingBatchFailurePhase.PROVIDER_REJECTED,
    )
    assert result.error_code == "RAG_PROVIDER_REQUEST_REJECTED"
    assert result.cancelled_batch_count == 1
    with fixture.fixture.connect(context["database"]) as db:
        batches = db.execute(
            "SELECT batch_state,provider_request_ref,error_code FROM "
            "plm.rag_embedding_build_batches WHERE embedding_build_id=%s "
            "ORDER BY batch_ordinal",
            (context["planned"].embedding_build_id,),
        ).fetchall()
        records = db.execute(
            "SELECT count(*) FROM plm.rag_embedding_records WHERE "
            "embedding_index_id=%s",
            (context["planned"].embedding_index_id,),
        ).fetchone()[0]
    assert batches == [
        ("FAILED", None, "RAG_PROVIDER_REQUEST_REJECTED"),
        ("CANCELLED", None, "RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE"),
    ]
    assert records == 0
    print(
        "RAG_03_A04_P05_P03_PROVIDER_REJECTED_PASS: Windows 11/"
        "PostgreSQL18.6 closed a known Provider rejection without a fake "
        "response reference, vectors, retry, or real Provider I/O"
    )


def main() -> None:
    fixture.main(after_send=publish_failure)
    fixture.main(after_send=publish_provider_rejection)


if __name__ == "__main__":
    main()
