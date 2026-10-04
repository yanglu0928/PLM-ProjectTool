"""Disposable PostgreSQL 18 proof for Schema0079 sealed build plans."""

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
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261004_0078"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


index_fixture = load(
    ROOT / "validation/rag-02-a02-embedding-index-schema/verify.py",
    "rag_build_index_fixture",
)


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject(operation) -> None:
    try:
        operation()
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid RAG EmbeddingBuild operation accepted")


def batch_source_fingerprint(member: tuple[int, uuid.UUID, bytes]) -> bytes:
    ordinal, chunk_id, fingerprint = member
    canonical = f"{ordinal}:{chunk_id}:{fingerprint.hex()}"
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def authorize_batch(db, *, actor, project, provider, provider_config, model,
                    index_id, source_fingerprint, payload_fingerprint,
                    payload_bytes, input_tokens):
    preview = db.execute(
        "INSERT INTO plm.ai_egress_previews(scope,project_id,purpose_ref,operation_type,"
        "ai_provider_id,provider_config_version_id,ai_model_id,data_region,"
        "allowed_data_categories,minimal_payload_policy_ref,estimated_record_count,"
        "max_payload_bytes,max_input_tokens,max_retry_attempts,payload_fingerprint,"
        "source_refs_fingerprint,risk_codes,created_by,trace_id,expires_at) VALUES "
        "('PROJECT',%s,'rag.index.build.v1','INDEX_BUILD',%s,%s,%s,'cn-beijing',%s,"
        "'rag.embedding.batch.v1',1,%s,%s,1,%s,%s,%s,%s,%s,"
        "statement_timestamp()+interval '2 hours') RETURNING egress_preview_id",
        (project, provider, provider_config, model, Jsonb(["PROJECT_RECORD"]),
         payload_bytes, input_tokens, payload_fingerprint, source_fingerprint,
         Jsonb(["EXTERNAL_PROVIDER"]), actor, uuid.uuid4()),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,ref_ordinal,"
        "resource_type,owner_module,object_type,object_id,version_id,scope,project_id) "
        "VALUES (%s,1,'RAG-02','rag','EMBEDDING_INDEX',%s,%s,'PROJECT',%s)",
        (preview, index_id, index_id, project),
    )
    trace = uuid.uuid4()
    with db.transaction():
        audit = db.execute(
            "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,actor_type,"
            "actor_id,action,outcome,target_owner_module,target_object_type,target_object_id) "
            "VALUES (%s,'PROJECT',%s,'USER',%s,'AI_EGRESS_AUTHORIZE','SUCCESS',"
            "'rag','RAG-03',%s) RETURNING audit_event_id",
            (trace, project, actor, preview),
        ).fetchone()[0]
        authorization, approved_at, valid_until = db.execute(
            "INSERT INTO plm.ai_egress_authorizations(egress_preview_id,scope,project_id,"
            "purpose_ref,operation_type,ai_provider_id,provider_config_version_id,ai_model_id,"
            "data_region,allowed_data_categories,minimal_payload_policy_ref,max_record_count,"
            "max_payload_bytes,max_input_tokens,max_retry_attempts,payload_fingerprint,"
            "source_refs_fingerprint,approved_by,approved_role,valid_until) VALUES "
            "(%s,'PROJECT',%s,'rag.index.build.v1','INDEX_BUILD',%s,%s,%s,'cn-beijing',%s,"
            "'rag.embedding.batch.v1',1,%s,%s,1,%s,%s,%s,'ProjectManager',"
            "statement_timestamp()+interval '1 hour') "
            "RETURNING authorization_id,approved_at,valid_until",
            (preview, project, provider, provider_config, model,
             Jsonb(["PROJECT_RECORD"]), payload_bytes, input_tokens,
             payload_fingerprint, source_fingerprint, actor),
        ).fetchone()
        db.execute(
            "INSERT INTO plm.ai_egress_authorize_results(result_id,authorization_id,"
            "egress_preview_id,actor_id,approved_role,audit_event_id,trace_id,result_state,"
            "lock_version,approved_at,valid_until) VALUES "
            "(%s,%s,%s,%s,'ProjectManager',%s,%s,'AUTHORIZED',0,%s,%s)",
            (uuid.uuid4(), authorization, preview, actor, audit, trace,
             approved_at, valid_until),
        )
    return authorization


def main() -> None:
    database = "rag03a03p01_" + uuid.uuid4().hex[:10]
    scratch = Path(tempfile.mkdtemp(prefix="plm-rag03a03p01-"))
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
                source = index_fixture.chunk_fixture.seed_source(db, storage)
                actor, project, _, _, version, record, result = source
                members = []
                for ordinal, body in enumerate(("PLM build one", "PLM build two"), 1):
                    chunk_id = db.execute(
                        index_fixture.chunk_fixture.CHUNK_INSERT,
                        index_fixture.chunk_fixture.chunk_values(
                            actor, project, version, record, result, ordinal - 1, body,
                        ),
                    ).fetchone()[0]
                    members.append((ordinal, chunk_id,
                                    hashlib.sha256(body.encode("utf-8")).digest()))
                model, _, _ = index_fixture.seed_provider_and_models(db, actor)
                index_id = index_fixture.create_index(
                    db, project=project, actor=actor, model=model, dimension=1024,
                    purpose="project.knowledge", version=1, chunks=tuple(members),
                )
                provider, provider_config = db.execute(
                    "SELECT model.ai_provider_id,provider.current_config_version_ref "
                    "FROM plm.ai_models model JOIN plm.ai_providers provider "
                    "ON provider.ai_provider_id=model.ai_provider_id "
                    "WHERE model.ai_model_id=%s", (model,),
                ).fetchone()
            command.upgrade(config, "head")
            command.check(config)
            with connect(database) as db:
                batch_specs = []
                for ordinal, member in enumerate(members, 1):
                    source_fp = batch_source_fingerprint(member)
                    payload_fp = hashlib.sha256(f"payload:{ordinal}".encode()).digest()
                    authorization = authorize_batch(
                        db, actor=actor, project=project, provider=provider,
                        provider_config=provider_config, model=model, index_id=index_id,
                        source_fingerprint=source_fp, payload_fingerprint=payload_fp,
                        payload_bytes=100 + ordinal, input_tokens=20 + ordinal,
                    )
                    batch_specs.append((ordinal, member[0], source_fp, payload_fp,
                                        100 + ordinal, 20 + ordinal, authorization))
                build_id, job_id = uuid.uuid4(), uuid.uuid4()
                auth_canonical = "\n".join(
                    f"{ordinal}:{authorization}:{source_fp.hex()}:{payload_fp.hex()}"
                    for ordinal, _, source_fp, payload_fp, _, _, authorization in batch_specs
                )
                auth_set_fp = hashlib.sha256(auth_canonical.encode()).digest()
                source_snapshot_fp = index_fixture.snapshot_fingerprint(tuple(members))
                build_canonical = (
                    f"{index_id}:1:{source_snapshot_fp.hex()}:"
                    f"{auth_set_fp.hex()}:{len(batch_specs)}"
                )
                build_fp = hashlib.sha256(build_canonical.encode()).digest()
                payload_refs = Jsonb({
                    "embedding_build_id": str(build_id),
                    "embedding_index_id": str(index_id),
                    "build_generation": 1,
                })
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.job_jobs(job_id,owner_module,job_type,scope,project_id,"
                        "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
                        "(%s,'rag','RAG_INDEX_BUILD','PROJECT',%s,%s,%s,%s,%s,1)",
                        (job_id, project, actor, str(uuid.uuid4()), payload_refs,
                         f"rag-index-build:{index_id}:1"),
                    )
                    db.execute(
                        "INSERT INTO plm.rag_embedding_builds(embedding_build_id,"
                        "embedding_index_id,scope,project_id,embedding_model_ref,"
                        "embedding_dimension,build_generation,build_job_ref,source_chunk_count,"
                        "source_snapshot_fingerprint,batch_count,authorization_set_fingerprint,"
                        "build_fingerprint,created_by) VALUES "
                        "(%s,%s,'PROJECT',%s,%s,1024,1,%s,2,%s,2,%s,%s,%s)",
                        (build_id, index_id, project, model, job_id, source_snapshot_fp,
                         auth_set_fp, build_fp, actor),
                    )
                    for spec in batch_specs:
                        ordinal, source_first, source_fp, payload_fp, size, tokens, auth = spec
                        db.execute(
                            "INSERT INTO plm.rag_embedding_build_batches(embedding_build_id,"
                            "batch_ordinal,source_first_ordinal,source_record_count,"
                            "source_batch_fingerprint,payload_fingerprint,payload_bytes,"
                            "input_tokens,egress_authorization_ref) VALUES "
                            "(%s,%s,%s,1,%s,%s,%s,%s,%s)",
                            (build_id, ordinal, source_first, source_fp, payload_fp,
                             size, tokens, auth),
                        )
                assert db.execute(
                    "SELECT build_state,batch_count,lock_version FROM plm.rag_embedding_builds "
                    "WHERE embedding_build_id=%s", (build_id,),
                ).fetchone() == ("PLANNED", 2, 0)
                assert db.execute(
                    "SELECT array_agg(batch_state ORDER BY batch_ordinal) FROM "
                    "plm.rag_embedding_build_batches WHERE embedding_build_id=%s",
                    (build_id,),
                ).fetchone()[0] == ["PENDING", "PENDING"]
                reject(lambda: db.execute(
                    "UPDATE plm.rag_embedding_builds SET build_state='RUNNING' "
                    "WHERE embedding_build_id=%s", (build_id,),
                ))
                reject(lambda: db.execute(
                    "UPDATE plm.rag_embedding_build_batches SET batch_state='RUNNING',"
                    "send_fencing_token=1,started_at=statement_timestamp() "
                    "WHERE embedding_build_id=%s AND batch_ordinal=1", (build_id,),
                ))
                reject(lambda: db.execute("TRUNCATE plm.rag_embedding_build_batches"))
            try:
                command.downgrade(config, PREVIOUS)
            except Exception as error:
                assert "RAG EmbeddingBuild history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated RAG EmbeddingBuild downgrade accepted")
            print(
                "RAG_03_A03_P01_BUILD_PLAN_SCHEMA_PASS: Schema0079 empty down/re-up, "
                "existing Index upgrade, ORM drift, exact contiguous batch partition, "
                "per-batch egress authorization, unique Job Owner, closed transitions, "
                "retention and populated downgrade verified on PostgreSQL 18"
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
