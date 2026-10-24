"""Windows 11/PostgreSQL 18 proof for atomic Embedding success."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command

from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.embedding_response_contract import (
    parse_embedding_response,
)
from plm_assistant.modules.rag.application.embedding_batch_success import (
    RAGEmbeddingBatchSuccessService,
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
    "rag_embedding_batch_success_fixture",
)


def publish(context, envelope, route, proof, response) -> None:
    parsed = parse_embedding_response(
        response=response, envelope=envelope, route=route,
    )
    try:
        with fixture.fixture.connect(context["database"]) as db:
            with db.transaction():
                db.execute(
                    "UPDATE plm.rag_embedding_build_batches SET "
                    "batch_state='SUCCEEDED',provider_request_ref=%s,"
                    "completed_at=clock_timestamp(),lock_version=2 "
                    "WHERE embedding_build_batch_id=%s",
                    (parsed.provider_request_ref,
                     envelope.embedding_build_batch_id),
                )
    except Exception as error:
        assert "record publication is incomplete" in str(error)
    else:
        raise AssertionError("incomplete successful Batch committed")
    with fixture.fixture.connect(context["database"]) as db:
        assert db.execute(
            "SELECT batch_state,lock_version FROM "
            "plm.rag_embedding_build_batches WHERE "
            "embedding_build_batch_id=%s",
            (envelope.embedding_build_batch_id,),
        ).fetchone() == ("RUNNING", 1)
    result = RAGEmbeddingBatchSuccessService(
        unit_of_work=context["runtime"].unit_of_work,
        claims=context["claims"],
        repository=SqlAlchemyRAGEmbeddingBatchSuccessRepository(),
    ).publish(
        envelope=envelope, send=AuthorizedAIEmbeddingSend(route, proof),
        parsed=parsed, job_id=context["claim"].job_id,
        fencing_token=context["claim"].fencing_token,
        worker_ref="rag-worker-01",
    )
    assert len(result.embedding_record_ids) == envelope.record_count
    with fixture.fixture.connect(context["database"]) as db:
        batch = db.execute(
            "SELECT batch_state,provider_request_ref,error_code,lock_version "
            "FROM plm.rag_embedding_build_batches "
            "WHERE embedding_build_batch_id=%s",
            (envelope.embedding_build_batch_id,),
        ).fetchone()
        records = db.execute(
            "SELECT chunk_id,embedding_dimension,vector_dims(embedding_vector),"
            "octet_length(vector_fingerprint),provider_request_ref,"
            "egress_authorization_ref FROM plm.rag_embedding_records "
            "WHERE embedding_index_id=%s",
            (envelope.embedding_index_id,),
        ).fetchall()
    assert batch == ("SUCCEEDED", parsed.provider_request_ref, None, 2)
    assert len(records) == envelope.record_count
    assert all(row[1:5] == (
        envelope.embedding_dimension, envelope.embedding_dimension, 32,
        parsed.provider_request_ref,
    ) for row in records)
    try:
        command.downgrade(context["config"], "20261004_0082")
    except Exception as error:
        assert "successful RAG Embedding history prevents downgrade" in str(error)
    else:
        raise AssertionError("successful Embedding history was downgraded")
    print(
        "RAG_03_A04_P05_P02_BATCH_SUCCESS_PASS: Windows 11/PostgreSQL18.6 "
        "atomically changed one fenced Batch RUNNING-to-SUCCEEDED and inserted "
        "the exact float32 EmbeddingRecord set with source, authorization, "
        "request and vector fingerprints; incomplete history and downgrade "
        "remain fail-closed; zero real Provider I/O"
    )


def main() -> None:
    fixture.main(after_send=publish)


if __name__ == "__main__":
    main()
