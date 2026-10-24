"""Disposable PostgreSQL 18 proof for Schema0077 EmbeddingIndex foundation."""

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
PREVIOUS = "20261004_0076"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


chunk_fixture = load(
    ROOT / "validation/rag-01-a02-document-chunk-schema/verify.py",
    "rag_index_chunk_fixture",
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
    raise AssertionError("invalid RAG EmbeddingIndex operation accepted")


def snapshot_fingerprint(chunks: tuple[tuple[int, uuid.UUID, bytes], ...]) -> bytes:
    canonical = "\n".join(
        f"{ordinal}:{chunk_id}:{fingerprint.hex()}"
        for ordinal, chunk_id, fingerprint in chunks
    )
    return hashlib.sha256(canonical.encode("utf-8")).digest()


INDEX_INSERT = """
INSERT INTO plm.rag_embedding_indexes(
 scope,project_id,index_purpose,embedding_model_ref,embedding_dimension,
 chunk_profile,chunk_profile_version,source_chunk_count,
 source_snapshot_fingerprint,index_version,created_by)
VALUES ('PROJECT',%s,%s,%s,%s,'paragraph.v1',1,%s,%s,%s,%s)
RETURNING embedding_index_id
"""


SOURCE_INSERT = """
INSERT INTO plm.rag_index_source_chunks(
 embedding_index_id,source_ordinal,chunk_id,scope,project_id,
 chunk_text_fingerprint)
VALUES (%s,%s,%s,'PROJECT',%s,%s)
"""


def create_index(db, *, project, actor, model, dimension, purpose, version,
                 chunks, fingerprint=None):
    digest = snapshot_fingerprint(chunks) if fingerprint is None else fingerprint
    with db.transaction():
        index_id = db.execute(
            INDEX_INSERT,
            (project, purpose, model, dimension, len(chunks), digest, version, actor),
        ).fetchone()[0]
        for ordinal, chunk_id, text_fingerprint in chunks:
            db.execute(
                SOURCE_INSERT,
                (index_id, ordinal, chunk_id, project, text_fingerprint),
            )
    return index_id


def seed_provider_and_models(db, actor):
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
        (actor,),
    ).fetchone()[0]
    provider, config = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
            "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
            (provider, config, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_provider_config_versions("
            "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,"
            "display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,"
            "can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES "
            "(%s,%s,1,'OPENAI_COMPATIBLE','Synthetic RAG Provider',"
            "'endpoint.synthetic.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
            "true,true,true,true,%s)",
            (config, provider, secret, actor),
        )
    embedding = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,embedding_dimension,created_by) VALUES "
        "(%s,'embed-rag-1024','EMBEDDING','rev-1',1024,%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    suspended = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,embedding_dimension,created_by) VALUES "
        "(%s,'embed-rag-suspended','EMBEDDING','rev-1',1024,%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    chat = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,created_by) VALUES "
        "(%s,'chat-rag','CHAT','rev-1',%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.ai_models SET model_state='AVAILABLE',lock_version=1 "
        "WHERE ai_model_id=%s", (embedding,),
    )
    return embedding, suspended, chat


def main() -> None:
    database = "rag02a02_" + uuid.uuid4().hex[:12]
    scratch = Path(tempfile.mkdtemp(prefix="plm-rag02a02-"))
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT,
                database=database,
            ))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, PREVIOUS)
            command.upgrade(config, PREVIOUS)
            storage = LocalParseResultStorage(scratch)
            with connect(database) as db:
                source = chunk_fixture.seed_source(db, storage)
                actor, project, other, _, version, record, result = source
                bodies = ("plm project capability", "plm requirement baseline")
                chunks = []
                for ordinal, body in enumerate(bodies):
                    chunk_id = db.execute(
                        chunk_fixture.CHUNK_INSERT,
                        chunk_fixture.chunk_values(
                            actor, project, version, record, result, ordinal, body,
                        ),
                    ).fetchone()[0]
                    chunks.append((ordinal + 1, chunk_id,
                                   hashlib.sha256(body.encode("utf-8")).digest()))
                models = seed_provider_and_models(db, actor)
            command.upgrade(config, "head")
            command.check(config)
            with connect(database) as db:
                embedding, suspended, chat = models
                members = tuple(chunks)
                reject(db, lambda: db.execute(
                    INDEX_INSERT,
                    (project, "rag.missing", embedding, 1024, len(members),
                     snapshot_fingerprint(members), 1, actor),
                ))
                reject(db, lambda: create_index(
                    db, project=project, actor=actor, model=suspended,
                    dimension=1024, purpose="rag.suspended", version=1,
                    chunks=members,
                ))
                reject(db, lambda: create_index(
                    db, project=project, actor=actor, model=chat,
                    dimension=1024, purpose="rag.chat", version=1,
                    chunks=members,
                ))
                reject(db, lambda: create_index(
                    db, project=project, actor=actor, model=embedding,
                    dimension=768, purpose="rag.dimension", version=1,
                    chunks=members,
                ))
                reject(db, lambda: create_index(
                    db, project=project, actor=actor, model=embedding,
                    dimension=1024, purpose="rag.bad-fingerprint", version=1,
                    chunks=members, fingerprint=b"x" * 32,
                ))
                reject(db, lambda: create_index(
                    db, project=other, actor=actor, model=embedding,
                    dimension=1024, purpose="rag.cross-project", version=1,
                    chunks=members,
                ))

                index_id = create_index(
                    db, project=project, actor=actor, model=embedding,
                    dimension=1024, purpose="project.knowledge", version=1,
                    chunks=members,
                )
                assert db.execute(
                    "SELECT index_state,source_chunk_count,lock_version FROM "
                    "plm.rag_embedding_indexes WHERE embedding_index_id=%s",
                    (index_id,),
                ).fetchone() == ("PLANNED", 2, 0)
                assert db.execute(
                    "SELECT array_agg(chunk_id ORDER BY source_ordinal) FROM "
                    "plm.rag_index_source_chunks WHERE embedding_index_id=%s",
                    (index_id,),
                ).fetchone()[0] == [members[0][1], members[1][1]]
                reject(db, lambda: db.execute(
                    SOURCE_INSERT,
                    (index_id, 3, members[0][1], project, members[0][2]),
                ))
                reject(db, lambda: db.execute(
                    "UPDATE plm.rag_embedding_indexes SET index_state='BUILDING',"
                    "lock_version=1 WHERE embedding_index_id=%s", (index_id,),
                ))
                reject(db, lambda: db.execute(
                    "UPDATE plm.rag_index_source_chunks SET project_id=%s "
                    "WHERE embedding_index_id=%s AND source_ordinal=1",
                    (other, index_id),
                ))
                reject(db, lambda: db.execute(
                    "DELETE FROM plm.rag_embedding_indexes WHERE embedding_index_id=%s",
                    (index_id,),
                ))
                reject(db, lambda: db.execute("TRUNCATE plm.rag_index_source_chunks"))
                reject(db, lambda: create_index(
                    db, project=project, actor=actor, model=embedding,
                    dimension=1024, purpose="project.knowledge", version=1,
                    chunks=members,
                ))
            try:
                command.downgrade(config, PREVIOUS)
            except Exception as error:
                assert "RAG EmbeddingIndex history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated RAG EmbeddingIndex downgrade accepted")
            print(
                "RAG_02_A02_EMBEDDING_INDEX_SCHEMA_PASS: Schema0077 empty down/re-up, "
                "existing Chunk/AIModel upgrade, ORM drift, model/scope/dimension/exact "
                "snapshot guards, creation seal, closed state changes, retention and "
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
