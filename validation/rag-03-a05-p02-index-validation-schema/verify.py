"""Windows 11/PostgreSQL 18 proof for Schema0085 validation evidence."""

from __future__ import annotations

import hashlib
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
    "rag_index_validation_worker_fixture",
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
    database = "rag03a05p02empty_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT,
                database=database,
            ))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20261004_0084")
            command.upgrade(config, "head")
            command.check(config)
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))


def validate(context, envelope, service, adapter) -> None:
    result = worker_fixture._run(context, envelope, service)
    assert result.state == "BATCH_SUCCEEDED"
    assert len(adapter.calls) == 1
    database = context["database"]
    planned = context["planned"]
    actor = context["actor"]
    project = context["project"]

    with begin_fixture.connect(database) as db:
        db.execute("ANALYZE plm.rag_embedding_records")
        query_vector = "[" + ",".join(["0.01"] * envelope.embedding_dimension) + "]"
        db.execute("SET hnsw.ef_search=200")
        db.execute("SET hnsw.iterative_scan='strict_order'")
        db.execute("SET enable_seqscan=off")
        db.execute("SET enable_sort=off")
        hnsw_plan = "\n".join(row[0] for row in db.execute(
            "EXPLAIN (COSTS OFF) SELECT embedding_record_id FROM "
            "plm.rag_embedding_records WHERE scope='PROJECT' AND project_id=%s "
            "AND embedding_index_id=%s AND embedding_state='AVAILABLE' "
            "AND embedding_dimension=1024 ORDER BY "
            "embedding_vector::vector(1024) <=> %s::vector(1024) LIMIT 1",
            (project, planned.embedding_index_id, query_vector),
        ))
        assert "ix_rag_embeddings__v1024_hnsw" in hnsw_plan, hnsw_plan
        hnsw_rows = db.execute(
            "SELECT embedding_record_id FROM plm.rag_embedding_records "
            "WHERE scope='PROJECT' AND project_id=%s AND embedding_index_id=%s "
            "AND embedding_state='AVAILABLE' AND embedding_dimension=1024 "
            "ORDER BY embedding_vector::vector(1024) <=> %s::vector(1024) LIMIT 1",
            (project, planned.embedding_index_id, query_vector),
        ).fetchall()
        db.execute("SET enable_seqscan=on")
        db.execute("SET enable_sort=on")
        db.execute("SET enable_indexscan=off")
        db.execute("SET enable_bitmapscan=off")
        exact_plan = "\n".join(row[0] for row in db.execute(
            "EXPLAIN (COSTS OFF) SELECT embedding_record_id FROM "
            "plm.rag_embedding_records WHERE scope='PROJECT' AND project_id=%s "
            "AND embedding_index_id=%s AND embedding_state='AVAILABLE' "
            "AND embedding_dimension=1024 ORDER BY "
            "embedding_vector::vector(1024) <=> %s::vector(1024) LIMIT 1",
            (project, planned.embedding_index_id, query_vector),
        ))
        assert "Seq Scan" in exact_plan, exact_plan
        exact_rows = db.execute(
            "SELECT embedding_record_id FROM plm.rag_embedding_records "
            "WHERE scope='PROJECT' AND project_id=%s AND embedding_index_id=%s "
            "AND embedding_state='AVAILABLE' AND embedding_dimension=1024 "
            "ORDER BY embedding_vector::vector(1024) <=> %s::vector(1024) LIMIT 1",
            (project, planned.embedding_index_id, query_vector),
        ).fetchall()
        db.execute("RESET enable_indexscan")
        db.execute("RESET enable_bitmapscan")
        assert {row[0] for row in hnsw_rows} == {row[0] for row in exact_rows}

        facts = db.execute(
            "SELECT index_row.scope,index_row.project_id,index_row.embedding_model_ref,"
            "index_row.embedding_dimension,index_row.source_chunk_count,"
            "index_row.source_snapshot_fingerprint,build.build_fingerprint,"
            "build.batch_count,count(record.embedding_record_id) "
            "FROM plm.rag_embedding_indexes index_row "
            "JOIN plm.rag_embedding_builds build ON build.embedding_index_id="
            "index_row.embedding_index_id LEFT JOIN plm.rag_embedding_records record "
            "ON record.embedding_index_id=index_row.embedding_index_id "
            "AND record.embedding_state='AVAILABLE' "
            "WHERE index_row.embedding_index_id=%s GROUP BY index_row.scope,"
            "index_row.project_id,index_row.embedding_model_ref,"
            "index_row.embedding_dimension,index_row.source_chunk_count,"
            "index_row.source_snapshot_fingerprint,build.build_fingerprint,"
            "build.batch_count",
            (planned.embedding_index_id,),
        ).fetchone()
        record_set_fingerprint = db.execute(
            "SELECT sha256(convert_to(string_agg(source.source_ordinal::text || ':' || "
            "record.chunk_id::text || ':' || encode(record.vector_fingerprint,'hex'), "
            "E'\\n' ORDER BY source.source_ordinal),'UTF8')) FROM "
            "plm.rag_index_source_chunks source JOIN plm.rag_embedding_records record "
            "ON record.embedding_index_id=source.embedding_index_id AND "
            "record.chunk_id=source.chunk_id AND record.embedding_state='AVAILABLE' "
            "WHERE source.embedding_index_id=%s",
            (planned.embedding_index_id,),
        ).fetchone()[0]
        hnsw_catalog_fingerprint = db.execute(
            "SELECT sha256(convert_to(indexdef,'UTF8')) FROM pg_indexes "
            "WHERE schemaname='plm' AND tablename='rag_embedding_records' "
            "AND indexname='ix_rag_embeddings__v1024_hnsw'",
        ).fetchone()[0]
        plan_fingerprint = hashlib.sha256(
            (hnsw_plan + "\n---exact---\n" + exact_plan).encode("utf-8")
        ).digest()
        validation_fingerprint = hashlib.sha256(
            b"rag-index-technical-v1\0" + record_set_fingerprint
            + hnsw_catalog_fingerprint + plan_fingerprint
        ).digest()
        values = (
            planned.embedding_index_id, planned.embedding_build_id,
            facts[0], facts[1], facts[2], facts[3], facts[4], facts[8],
            facts[7], facts[7], facts[5], facts[6], record_set_fingerprint,
            hnsw_catalog_fingerprint, plan_fingerprint,
            validation_fingerprint, actor,
        )
        insert = (
            "INSERT INTO plm.rag_embedding_index_validations("
            "embedding_index_id,embedding_build_id,scope,project_id,"
            "embedding_model_ref,embedding_dimension,source_chunk_count,"
            "available_record_count,missing_record_count,extra_record_count,"
            "duplicate_record_count,invalid_record_count,expected_batch_count,"
            "succeeded_batch_count,source_snapshot_fingerprint,build_fingerprint,"
            "record_set_fingerprint,validation_policy_ref,hnsw_index_name,"
            "hnsw_catalog_fingerprint,hnsw_plan_observed,exact_plan_observed,"
            "hnsw_ef_search,hnsw_iterative_scan,exact_query_count,exact_top_k,"
            "exact_overlap_count,"
            "exact_expected_count,minimum_recall_basis_points,"
            "observed_recall_basis_points,plan_fingerprint,validation_fingerprint,"
            "validation_state,validated_by,completed_at) VALUES ("
            "%s,%s,%s,%s,%s,%s,%s,%s,0,0,0,0,%s,%s,%s,%s,%s,"
            "'rag-index-technical-v1','ix_rag_embeddings__v1024_hnsw',"
            "%s,true,true,200,'strict_order',1,1,1,1,10000,10000,%s,%s,'PASSED',%s,"
            "'2000-01-01T00:00:00Z') RETURNING embedding_index_validation_id"
        )
        bad = list(values)
        bad[12] = b"x" * 32
        reject_db(db, lambda: db.execute(insert, tuple(bad)),
                  "observed facts are invalid")
        bad = list(values)
        bad[15] = b"x" * 32
        reject_db(db, lambda: db.execute(insert, tuple(bad)),
                  "fingerprint is invalid")
        validation_id = db.execute(insert, values).fetchone()[0]
        state = db.execute(
            "SELECT validation_state,available_record_count,missing_record_count,"
            "succeeded_batch_count,hnsw_plan_observed,exact_plan_observed,"
            "observed_recall_basis_points FROM "
            "plm.rag_embedding_index_validations WHERE "
            "embedding_index_validation_id=%s", (validation_id,),
        ).fetchone()
        assert state == ("PASSED", 1, 0, 1, True, True, 10000)
        assert db.execute(
            "SELECT completed_at>'2026-01-01T00:00:00Z' FROM "
            "plm.rag_embedding_index_validations WHERE "
            "embedding_index_validation_id=%s", (validation_id,),
        ).fetchone()[0]
        aggregate_state = db.execute(
            "SELECT index_state,build_state,job.state FROM "
            "plm.rag_embedding_indexes index_row JOIN plm.rag_embedding_builds build "
            "ON build.embedding_index_id=index_row.embedding_index_id JOIN "
            "plm.job_jobs job ON job.job_id=build.build_job_ref WHERE "
            "index_row.embedding_index_id=%s", (planned.embedding_index_id,),
        ).fetchone()
        assert aggregate_state == ("BUILDING", "RUNNING", "RUNNING")
        reject_db(db, lambda: db.execute(
            "UPDATE plm.rag_embedding_index_validations SET "
            "validation_state='FAILED',error_code='RAG_TEST' WHERE "
            "embedding_index_validation_id=%s", (validation_id,),
        ), "history is immutable")
        reject_db(db, lambda: db.execute(
            "DELETE FROM plm.rag_embedding_index_validations WHERE "
            "embedding_index_validation_id=%s", (validation_id,),
        ), "history is immutable")
        reject_db(db, lambda: db.execute(
            "TRUNCATE plm.rag_embedding_index_validations"
        ), "history cannot be truncated")

    try:
        command.downgrade(context["config"], "20261004_0084")
    except Exception as error:
        assert "history prevents downgrade" in str(error), str(error)
    else:
        raise AssertionError("populated IndexValidation downgrade accepted")
    print(
        "RAG_03_A05_P02_INDEX_VALIDATION_SCHEMA_PASS: Windows 11/"
        "PostgreSQL18.6 retained one immutable technical PASS bound to the exact "
        "Index/Build/records/batches/current lease, catalog HNSW and exact query "
        "evidence while keeping Build/Index/Job RUNNING/BUILDING; zero real "
        "Provider I/O"
    )


def main() -> None:
    verify_empty_migration()
    send_fixture.main(
        execute=validate,
        source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
