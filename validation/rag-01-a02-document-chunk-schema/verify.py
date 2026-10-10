"""Disposable PostgreSQL 18 proof for Schema0076 RAG DocumentChunk."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261003_0075"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


document_fixture = load(
    ROOT / "validation/ai-04-a06-p03-p02-a03-document-content-pg/verify.py",
    "rag_document_fixture",
)


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid RAG DocumentChunk operation accepted")


CHUNK_INSERT = """
INSERT INTO plm.rag_document_chunks(
 scope,project_id,document_version_ref,parse_record_ref,parse_result_ref,
 chunk_profile,chunk_profile_version,chunk_ordinal,source_locator,source_type,
 search_body,text_fingerprint,metadata_snapshot,created_by)
VALUES ('PROJECT',%s,%s,%s,%s,'paragraph.v1',1,%s,%s,'PROJECT_RECORD',%s,%s,%s,%s)
RETURNING chunk_id
"""


def seed_source(db: psycopg.Connection, storage: LocalParseResultStorage):
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES ('Synthetic RAG Builder','synthetic rag builder') RETURNING user_id",
    ).fetchone()[0]
    project = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES ('RAGA02','raga02','Synthetic RAG Source',%s) RETURNING project_id",
        (actor,),
    ).fetchone()[0]
    other = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES ('RAGOTH','ragoth','Other RAG Project',%s) RETURNING project_id",
        (actor,),
    ).fetchone()[0]
    source = "PLM capability 项目 能力 基线与差异".encode("utf-8")
    source_hash = hashlib.sha256(source).digest()
    document = db.execute(
        "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
        "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
        "'Synthetic RAG source','rag-source.txt',%s) RETURNING document_id",
        (project, actor),
    ).fetchone()[0]
    file_id = db.execute(
        "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,"
        "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,"
        "available_at) VALUES ('PROJECT',%s,'PERSISTENT','projects/rag/source',"
        "'rag-source.txt',%s,'AVAILABLE',%s,%s,'text/plain',statement_timestamp()) "
        "RETURNING file_object_id",
        (project, actor, source_hash, len(source)),
    ).fetchone()[0]
    version = db.execute(
        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
        "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
        "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
        "RETURNING document_version_id",
        (document, project, file_id, source_hash, len(source), Jsonb({}), actor),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
        "WHERE document_id=%s", (version, version, document),
    )
    record, result, _ = document_fixture.seed_result(
        db, storage, actor=actor, project=project, document=document,
        version=version, source_sha=source_hash, attempt=1,
        text=source.decode("utf-8"), completed_at=datetime.now(timezone.utc),
    )
    return actor, project, other, document, version, record, result


def chunk_values(actor, project, version, record, result, ordinal, body):
    return (
        project, version, record, result, ordinal,
        Jsonb({"locator_type": "PARSED_NODE", "node_id": "synthetic-1"}),
        body, hashlib.sha256(body.encode("utf-8")).digest(),
        Jsonb({"language": "zh-CN", "heading_path": []}), actor,
    )


def main() -> None:
    database = "rag01a02_" + uuid.uuid4().hex[:12]
    scratch = Path(tempfile.mkdtemp(prefix="plm-rag01a02-"))
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
                source = seed_source(db, storage)
            command.upgrade(config, "head")
            command.check(config)
            with connect(database) as db:
                actor, project, other, _, version, record, result = source
                assert db.execute(
                    "SELECT count(*) FROM plm.rag_document_chunks",
                ).fetchone() == (0,)
                body = "plm capability 项目 能力"
                values = chunk_values(
                    actor, project, version, record, result, 0, body,
                )
                reject(db, CHUNK_INSERT, (
                    other, *values[1:],
                ))
                reject(db, CHUNK_INSERT, (
                    *values[:7], b"x" * 32, *values[8:],
                ))
                chunk = db.execute(CHUNK_INSERT, values).fetchone()[0]
                second_body = "plm standard capability reference"
                second = db.execute(CHUNK_INSERT, chunk_values(
                    actor, project, version, record, result, 1, second_body,
                )).fetchone()[0]
                reject(db, CHUNK_INSERT, values)
                assert db.execute(
                    "SELECT count(*) FROM plm.rag_document_chunks WHERE "
                    "project_id=%s AND search_vector @@ "
                    "to_tsquery('simple','plm & capability')", (project,),
                ).fetchone() == (2,)
                db.execute("SET enable_seqscan=off")
                plan = "\n".join(row[0] for row in db.execute(
                    "EXPLAIN SELECT chunk_id FROM plm.rag_document_chunks WHERE "
                    "search_vector @@ to_tsquery('simple','plm & capability')",
                ).fetchall())
                assert "ix_rag_chunks__search_gin" in plan, plan
                reject(
                    db,
                    "UPDATE plm.rag_document_chunks SET search_body='changed',"
                    "text_fingerprint=sha256(convert_to('changed','UTF8')),lock_version=1 "
                    "WHERE chunk_id=%s", (chunk,),
                )
                db.execute(
                    "UPDATE plm.doc_documents SET effective_version_ref=NULL "
                    "WHERE effective_version_ref=%s", (version,),
                )
                db.execute(
                    "UPDATE plm.doc_document_versions SET availability_state='RESTRICTED' "
                    "WHERE document_version_id=%s", (version,),
                )
                db.execute(
                    "UPDATE plm.rag_document_chunks SET chunk_state='RESTRICTED',"
                    "lock_version=1 WHERE chunk_id=%s", (chunk,),
                )
                reject(
                    db,
                    "UPDATE plm.rag_document_chunks SET chunk_state='ACTIVE',"
                    "lock_version=2 WHERE chunk_id=%s", (chunk,),
                )
                db.execute(
                    "UPDATE plm.doc_document_versions SET availability_state='REVOKED' "
                    "WHERE document_version_id=%s", (version,),
                )
                db.execute(
                    "UPDATE plm.rag_document_chunks SET chunk_state='REVOKED',"
                    "lock_version=2 WHERE chunk_id=%s", (chunk,),
                )
                db.execute(
                    "UPDATE plm.rag_document_chunks SET chunk_state='REVOKED',"
                    "lock_version=1 WHERE chunk_id=%s", (second,),
                )
                reject(db, "DELETE FROM plm.rag_document_chunks WHERE chunk_id=%s", (chunk,))
                reject(db, "TRUNCATE plm.rag_document_chunks")
            try:
                command.downgrade(config, PREVIOUS)
            except Exception as error:
                assert "RAG DocumentChunk history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated RAG DocumentChunk downgrade accepted")
            print(
                "RAG_01_A02_DOCUMENT_CHUNK_SCHEMA_PASS: Schema0076 empty down/re-up, "
                "existing Document/Parse upgrade, ORM drift, source/scope/hash/generation "
                "guards, controlled simple FTS with GIN plan, retention and populated "
                "downgrade verified on PostgreSQL 18"
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
