"""Windows 11/PostgreSQL 18 proof for validated READY convergence."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.rag.application.embedding_index_validation import (
    RAGEmbeddingIndexValidationService,
)
from plm_assistant.modules.rag.infrastructure.embedding_index_validation_repository import (
    SqlAlchemyRAGEmbeddingIndexValidationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker_fixture = load(
    ROOT / "validation/rag-03-a04-p06-batch-worker/verify.py",
    "rag_index_ready_worker_fixture",
)
send_fixture = worker_fixture.fixture
begin_fixture = send_fixture.fixture


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject_db(db, operation, expected: str) -> None:
    try:
        with db.transaction():
            operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"database operation unexpectedly succeeded: {expected}")


def verify_empty_migration() -> None:
    database = "rag03a05p03empty_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT,
                database=database,
            ))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20261004_0085")
            command.upgrade(config, "head")
            command.check(config)
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))


class _ForcedRecallFailureRepository(
        SqlAlchemyRAGEmbeddingIndexValidationRepository):
    @staticmethod
    def _probe(session, claim, dimension, available_count, policy):
        value = dict(SqlAlchemyRAGEmbeddingIndexValidationRepository._probe(
            session, claim, dimension, available_count, policy,
        ))
        value["overlap_count"] = 0
        value["observed_recall_basis_points"] = 0
        return value


def _execute(context, envelope, sender, adapter, *, force_failure: bool) -> None:
    worker_result = worker_fixture._run(context, envelope, sender)
    assert worker_result.state == "BATCH_SUCCEEDED"
    assert len(adapter.calls) == 1
    database = context["database"]
    planned = context["planned"]
    with begin_fixture.connect(database) as db:
        db.execute("ANALYZE plm.rag_embedding_records")
        reject_db(db, lambda: db.execute(
            "UPDATE plm.job_jobs SET state='SUCCEEDED',"
            "lease_expires_at=NULL,completed_at=clock_timestamp() "
            "WHERE job_id=%s", (planned.job_id,),
        ), "validated success transaction is incomplete")
        reject_db(db, lambda: db.execute(
            "UPDATE plm.rag_embedding_indexes SET index_state='READY',"
            "lock_version=2 WHERE embedding_index_id=%s",
            (planned.embedding_index_id,),
        ), "READY proof is invalid")

    repository = (_ForcedRecallFailureRepository() if force_failure
                  else SqlAlchemyRAGEmbeddingIndexValidationRepository())
    outcome = RAGEmbeddingIndexValidationService(
        unit_of_work=context["runtime"].unit_of_work,
        claims=context["claims"], repository=repository,
    ).validate(
        job_id=context["claim"].job_id, fencing_token=1,
        worker_ref="rag-worker-01",
    )
    expected = (("FAILED", "FAILED", "FAILED", "RELEASED",
                 "RAG_INDEX_TECHNICAL_VALIDATION_FAILED", "FAILED", 0)
                if force_failure else
                ("READY", "SUCCEEDED", "SUCCEEDED", "RELEASED",
                 None, "PASSED", 10000))
    with begin_fixture.connect(database) as db:
        state = db.execute(
            "SELECT index_row.index_state,build.build_state,job.state,lease.state,"
            "attempt.error_code,validation.validation_state,"
            "validation.observed_recall_basis_points FROM "
            "plm.rag_embedding_indexes index_row JOIN plm.rag_embedding_builds build "
            "ON build.embedding_index_id=index_row.embedding_index_id JOIN "
            "plm.job_jobs job ON job.job_id=build.build_job_ref JOIN "
            "plm.job_leases lease ON lease.job_id=job.job_id AND "
            "lease.fencing_token=1 JOIN plm.job_attempts attempt ON "
            "attempt.job_id=job.job_id AND attempt.fencing_token=1 JOIN "
            "plm.rag_embedding_index_validations validation ON "
            "validation.embedding_build_id=build.embedding_build_id WHERE "
            "index_row.embedding_index_id=%s",
            (planned.embedding_index_id,),
        ).fetchone()
        assert state == expected, state
        assert db.execute(
            "SELECT job.completed_at=attempt.completed_at AND "
            "job.completed_at>=validation.completed_at AND "
            "job.lease_expires_at IS NULL FROM plm.job_jobs job JOIN "
            "plm.job_attempts attempt ON attempt.job_id=job.job_id AND "
            "attempt.fencing_token=1 JOIN plm.rag_embedding_builds build ON "
            "build.build_job_ref=job.job_id JOIN "
            "plm.rag_embedding_index_validations validation ON "
            "validation.embedding_build_id=build.embedding_build_id WHERE "
            "job.job_id=%s", (planned.job_id,),
        ).fetchone()[0]
        assert db.execute(
            "SELECT count(*) FROM plm.rag_embedding_indexes WHERE "
            "embedding_index_id=%s AND index_state='ACTIVE'",
            (planned.embedding_index_id,),
        ).fetchone()[0] == 0
    assert outcome.validation_state == expected[5]
    assert outcome.index_state == expected[0]
    try:
        command.downgrade(context["config"], "20261004_0085")
    except Exception as error:
        assert "validated RAG READY history prevents downgrade" in str(error), error
    else:
        raise AssertionError("validated RAG terminal history accepted downgrade")


def execute_success(context, envelope, sender, adapter) -> None:
    _execute(context, envelope, sender, adapter, force_failure=False)
    print(
        "RAG_03_A05_P03_READY_PASS: technical PASS atomically completed "
        "Job/Attempt/Lease/Build and advanced only Index READY"
    )


def execute_failure(context, envelope, sender, adapter) -> None:
    _execute(context, envelope, sender, adapter, force_failure=True)
    print(
        "RAG_03_A05_P03_FAILURE_PASS: controlled Recall failure retained "
        "immutable evidence and atomically closed Job/Build/Index FAILED"
    )


def main() -> None:
    verify_empty_migration()
    send_fixture.main(
        execute=execute_success, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )
    send_fixture.main(
        execute=execute_failure, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
