"""Disposable PostgreSQL 18 proof for Schema0078 EmbeddingRecord/HNSW."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261004_0077"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


index_fixture = load(
    ROOT / "validation/rag-02-a02-embedding-index-schema/verify.py",
    "rag_embedding_record_index_fixture",
)


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject(db: psycopg.Connection, operation) -> None:
    try:
        with db.transaction():
            operation()
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid RAG EmbeddingRecord operation accepted")


def explain_uses(db, *, dimension: int, vector: str, expected: str) -> None:
    db.execute("SET enable_seqscan=off")
    plan = "\n".join(row[0] for row in db.execute(
        "EXPLAIN (COSTS OFF) SELECT embedding_record_id "
        "FROM plm.rag_embedding_records "
        "WHERE embedding_state='AVAILABLE' AND embedding_dimension=%s "
        f"ORDER BY embedding_vector::vector({dimension}) <=> %s::vector({dimension}) LIMIT 5",
        (dimension, vector),
    ))
    assert expected in plan, plan


def main() -> None:
    database = "rag03a02_" + uuid.uuid4().hex[:12]
    scratch = Path(tempfile.mkdtemp(prefix="plm-rag03a02-"))
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT,
                database=database,
            ))
            command.upgrade(config, "head")
            command.check(config)
            with connect(database) as db:
                indexes = {
                    row[0]: row[1]
                    for row in db.execute(
                        "SELECT indexname,indexdef FROM pg_indexes "
                        "WHERE schemaname='plm' AND tablename='rag_embedding_records'"
                    )
                }
                for dimension in (768, 1024):
                    definition = indexes[f"ix_rag_embeddings__v{dimension}_hnsw"]
                    assert "USING hnsw" in definition
                    assert f"vector({dimension})" in definition
                    assert "vector_cosine_ops" in definition
                assert db.execute(
                    "SELECT extversion FROM pg_extension WHERE extname='vector'"
                ).fetchone() == ("0.8.6",)

            command.downgrade(config, PREVIOUS)
            command.upgrade(config, PREVIOUS)
            storage = LocalParseResultStorage(scratch)
            with connect(database) as db:
                source = index_fixture.chunk_fixture.seed_source(db, storage)
                actor, project, _, _, version, record, result = source
                body = "plm controlled embedding record"
                chunk = db.execute(
                    index_fixture.chunk_fixture.CHUNK_INSERT,
                    index_fixture.chunk_fixture.chunk_values(
                        actor, project, version, record, result, 0, body,
                    ),
                ).fetchone()[0]
                model, _, _ = index_fixture.seed_provider_and_models(db, actor)
                fingerprint = hashlib.sha256(body.encode("utf-8")).digest()
                index_id = index_fixture.create_index(
                    db, project=project, actor=actor, model=model,
                    dimension=1024, purpose="project.knowledge", version=1,
                    chunks=((1, chunk, fingerprint),),
                )
            command.upgrade(config, "head")
            command.check(config)
            with connect(database) as db:
                reject(db, lambda: db.execute(
                    "INSERT INTO plm.rag_embedding_records("
                    "scope,project_id,embedding_index_id,chunk_id,embedding_model_ref,"
                    "embedding_dimension,chunk_text_fingerprint,embedding_vector,"
                    "vector_fingerprint,egress_authorization_ref) VALUES "
                    "('PROJECT',%s,%s,%s,%s,1024,%s,%s::vector,%s,%s)",
                    (project, index_id, chunk, model, fingerprint,
                     "[" + ",".join(["0"] * 1024) + "]", b"v" * 32, uuid.uuid4()),
                ))

                # Physical-only probe: future A03 owns BUILDING transitions and authorization.
                # Replica mode bypasses user/FK triggers in this disposable superuser database,
                # while PostgreSQL check constraints and HNSW maintenance remain active.
                db.execute("SET session_replication_role='replica'")
                vectors: dict[int, str] = {}
                for dimension in (768, 1024):
                    vector = "[" + ",".join(["0.01"] * dimension) + "]"
                    vectors[dimension] = vector
                    db.execute(
                        "INSERT INTO plm.rag_embedding_records("
                        "scope,embedding_index_id,chunk_id,embedding_model_ref,"
                        "embedding_dimension,chunk_text_fingerprint,embedding_vector,"
                        "vector_fingerprint,egress_authorization_ref) VALUES "
                        "('GLOBAL',%s,%s,%s,%s,%s,%s::vector,%s,%s)",
                        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), dimension,
                         b"c" * 32, vector, bytes([dimension % 251]) * 32, uuid.uuid4()),
                    )
                reject(db, lambda: db.execute(
                    "INSERT INTO plm.rag_embedding_records("
                    "scope,embedding_index_id,chunk_id,embedding_model_ref,"
                    "embedding_dimension,chunk_text_fingerprint,embedding_vector,"
                    "vector_fingerprint,egress_authorization_ref) VALUES "
                    "('GLOBAL',%s,%s,%s,768,%s,%s::vector,%s,%s)",
                    (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), b"c" * 32,
                     vectors[1024], b"x" * 32, uuid.uuid4()),
                ))
                db.execute("SET session_replication_role='origin'")
                db.execute("ANALYZE plm.rag_embedding_records")
                explain_uses(
                    db, dimension=768, vector=vectors[768],
                    expected="ix_rag_embeddings__v768_hnsw",
                )
                explain_uses(
                    db, dimension=1024, vector=vectors[1024],
                    expected="ix_rag_embeddings__v1024_hnsw",
                )
                record_id = db.execute(
                    "SELECT embedding_record_id FROM plm.rag_embedding_records LIMIT 1"
                ).fetchone()[0]
                reject(db, lambda: db.execute(
                    "UPDATE plm.rag_embedding_records SET embedding_state='REVOKED' "
                    "WHERE embedding_record_id=%s", (record_id,),
                ))
                reject(db, lambda: db.execute(
                    "DELETE FROM plm.rag_embedding_records WHERE embedding_record_id=%s",
                    (record_id,),
                ))
                reject(db, lambda: db.execute("TRUNCATE plm.rag_embedding_records"))
            try:
                command.downgrade(config, PREVIOUS)
            except Exception as error:
                assert "RAG EmbeddingRecord history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated RAG EmbeddingRecord downgrade accepted")
            print(
                "RAG_03_A02_EMBEDDING_RECORD_SCHEMA_PASS: Schema0078 empty down/re-up, "
                "existing Index upgrade, ORM drift, PLANNED write closure, controlled "
                "768/1024 HNSW physical plans, vector dimension checks, retention and "
                "populated downgrade verified on PostgreSQL 18"
            )
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))
            shutil.rmtree(scratch)
    assert not scratch.exists()


if __name__ == "__main__":
    main()
