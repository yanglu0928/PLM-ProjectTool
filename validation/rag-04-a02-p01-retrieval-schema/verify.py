"""Windows 11/PostgreSQL 18 proof for Schema0088 Retrieval foundation."""

from __future__ import annotations

import uuid
import importlib.util
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


activation_fixture = load(
    ROOT / "validation/rag-03-a05-p04-p04-index-activation/verify.py",
    "rag_retrieval_activation_fixture",
)


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def config(database: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    ))


def create_database(prefix: str) -> str:
    database = prefix + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    return database


def drop_database(database: str) -> None:
    with connect("postgres") as admin:
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
        )
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(database)))


def verify_empty_and_existing_upgrade() -> None:
    database = create_database("rag04a02p01_")
    try:
        cfg = config(database)
        command.upgrade(cfg, "20261004_0087")
        actor, project = uuid.uuid4(), uuid.uuid4()
        with connect(database) as db:
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized,state,deployment_role) "
                "VALUES (%s,'retrieval schema actor','retrieval-schema-actor',"
                "'DISABLED','NONE')", (actor,),
            )
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,state,created_by) "
                "VALUES (%s,'RAG-0088','rag-0088','RAG schema fixture',"
                "'ACTIVE',%s)", (project, actor),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.prj_projects WHERE project_id=%s",
                (project,),
            ).fetchone()[0] == 1
            names = {row[0] for row in db.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='plm' AND table_name LIKE 'rag_%'"
            )}
            assert {
                "rag_retrieval_runs", "rag_retrieval_query_contents",
                "rag_retrieval_candidates", "rag_retrieval_score_parts",
                "rag_context_bundles", "rag_context_items",
            } <= names
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='plm' "
                "AND table_name='rag_retrieval_query_contents'"
            )}
            assert "encrypted_payload" in columns
            assert "query_fingerprint" in columns
            assert not {"query_body", "query_text", "plaintext"} & columns
        command.downgrade(cfg, "20261004_0087")
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        drop_database(database)


def verify_history_refuses_downgrade() -> None:
    database = create_database("rag04a02p01hist_")
    try:
        cfg = config(database)
        command.upgrade(cfg, "head")
        run_id = uuid.uuid4()
        with connect(database) as db:
            db.execute("SET session_replication_role='replica'")
            db.execute("""
                INSERT INTO plm.rag_retrieval_runs(
                  retrieval_run_id,scope,project_id,actor_ref,query_fingerprint,
                  metadata_filter,metadata_filter_fingerprint,global_index_ref,
                  project_index_ref,retrieval_policy_ref,rerank_policy_ref,top_k,
                  rerank_state,egress_state,retrieval_state,quality_flags,
                  degraded,error_code,job_id,trace_id)
                VALUES (%s,'GLOBAL',NULL,%s,sha256('query'::bytea),'{}'::jsonb,
                  sha256('{}'::bytea),%s,NULL,'hybrid.v1','none.v1',5,
                  'NOT_APPLICABLE','NOT_APPLICABLE','RUNNING','[]'::jsonb,
                  false,NULL,%s,%s)
            """, (run_id, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()))
            db.execute("SET session_replication_role='origin'")
        try:
            command.downgrade(cfg, "20261004_0087")
        except Exception as error:
            assert "RAG Retrieval history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0088 downgrade accepted retained history")
    finally:
        drop_database(database)


def reject(db, operation, expected: str) -> None:
    try:
        with db.transaction():
            operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"database operation unexpectedly succeeded: {expected}")


def verify_bound_run_candidate_and_closed_context() -> None:
    def execute(context, envelope, sender, adapter) -> None:
        activation_fixture.execute(context, envelope, sender, adapter)
        database = context["database"]
        actor, project = context["actor"], context["project"]
        index_id = context["planned"].embedding_index_id
        run_id, job_id, trace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        query = "synthetic retrieval query"
        with activation_fixture.begin_fixture.connect(database) as db:
            with db.transaction():
                db.execute("""
                    INSERT INTO plm.job_jobs(
                      job_id,owner_module,job_type,scope,project_id,actor_ref,
                      trace_id,payload_refs,idempotency_key,max_attempts)
                    VALUES (%s,'rag','RAG_RETRIEVAL','PROJECT',%s,%s,%s,
                      jsonb_build_object('retrieval_run_id',%s::text),%s,1)
                """, (job_id, project, actor, str(trace_id), run_id,
                        str(uuid.uuid4())))
                db.execute("""
                    INSERT INTO plm.rag_retrieval_runs(
                      retrieval_run_id,scope,project_id,actor_ref,query_fingerprint,
                      metadata_filter,metadata_filter_fingerprint,global_index_ref,
                      project_index_ref,retrieval_policy_ref,rerank_policy_ref,top_k,
                      rerank_state,egress_state,retrieval_state,quality_flags,
                      degraded,error_code,job_id,trace_id)
                    VALUES (%s,'PROJECT',%s,%s,sha256(convert_to(%s,'UTF8')),
                      '{}'::jsonb,sha256('{}'::bytea),NULL,%s,
                      'hybrid.project.v1','none.v1',5,'NOT_APPLICABLE',
                      'NOT_APPLICABLE','RUNNING','[]'::jsonb,false,NULL,%s,%s)
                """, (run_id, project, actor, query, index_id, job_id, trace_id))
                db.execute("""
                    INSERT INTO plm.rag_retrieval_query_contents(
                      retrieval_run_id,project_id,query_fingerprint,
                      encrypted_payload,encryption_metadata,key_provider_ref,
                      plaintext_bytes,retention_until)
                    VALUES (%s,%s,sha256(convert_to(%s,'UTF8')),%s,
                      '{"format":"rag-query-aesgcm.v1","nonce":"synthetic"}'::jsonb,
                      'synthetic-key.v1',%s,statement_timestamp()+interval '1 day')
                """, (run_id, project, query, b"c" * 32, len(query.encode("utf-8"))))
            assert db.execute(
                "SELECT encrypted_payload<>convert_to(%s,'UTF8'),query_fingerprint="
                "sha256(convert_to(%s,'UTF8')) FROM plm.rag_retrieval_query_contents "
                "WHERE retrieval_run_id=%s", (query, query, run_id),
            ).fetchone() == (True, True)

            def missing_query():
                other_run, other_job, other_trace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                db.execute("""
                    INSERT INTO plm.job_jobs(
                      job_id,owner_module,job_type,scope,project_id,actor_ref,
                      trace_id,payload_refs,idempotency_key,max_attempts)
                    VALUES (%s,'rag','RAG_RETRIEVAL','PROJECT',%s,%s,%s,
                      jsonb_build_object('retrieval_run_id',%s::text),%s,1)
                """, (other_job, project, actor, str(other_trace), other_run,
                        str(uuid.uuid4())))
                db.execute("""
                    INSERT INTO plm.rag_retrieval_runs(
                      retrieval_run_id,scope,project_id,actor_ref,query_fingerprint,
                      metadata_filter,metadata_filter_fingerprint,global_index_ref,
                      project_index_ref,retrieval_policy_ref,rerank_policy_ref,top_k,
                      rerank_state,egress_state,retrieval_state,quality_flags,
                      degraded,error_code,job_id,trace_id)
                    VALUES (%s,'PROJECT',%s,%s,sha256('missing'::bytea),'{}'::jsonb,
                      sha256('{}'::bytea),NULL,%s,'hybrid.project.v1','none.v1',5,
                      'NOT_APPLICABLE','NOT_APPLICABLE','RUNNING','[]'::jsonb,
                      false,NULL,%s,%s)
                """, (other_run, project, actor, index_id, other_job, other_trace))

            reject(db, missing_query, "query content is incomplete")
            reject(db, lambda: db.execute(
                "UPDATE plm.rag_retrieval_runs SET lock_version=1 "
                "WHERE retrieval_run_id=%s", (run_id,),
            ), "state Owner is not installed")

            candidate_id = db.execute("""
                INSERT INTO plm.rag_retrieval_candidates(
                  retrieval_run_id,run_project_id,candidate_scope,
                  candidate_project_id,embedding_index_id,embedding_model_ref,
                  chunk_id,document_version_ref,parse_result_ref,source_type,
                  source_locator,retrieval_channel,candidate_ordinal,
                  final_score_micros,authorization_snapshot_fingerprint)
                SELECT %s,%s,chunk.scope,chunk.project_id,index_row.embedding_index_id,
                  index_row.embedding_model_ref,chunk.chunk_id,
                  chunk.document_version_ref,chunk.parse_result_ref,
                  chunk.source_type,chunk.source_locator,'HYBRID',0,900000,
                  sha256('synthetic access snapshot'::bytea)
                FROM plm.rag_embedding_indexes index_row
                JOIN plm.rag_index_source_chunks source
                  ON source.embedding_index_id=index_row.embedding_index_id
                JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
                WHERE index_row.embedding_index_id=%s
                ORDER BY source.source_ordinal LIMIT 1
                RETURNING candidate_id
            """, (run_id, project, index_id)).fetchone()[0]
            db.execute("""
                INSERT INTO plm.rag_retrieval_score_parts(
                  retrieval_run_id,project_id,candidate_id,score_kind,
                  score_ordinal,raw_score_micros,normalized_score_micros,
                  weight_micros,weighted_score_micros,score_policy_ref)
                VALUES (%s,%s,%s,'FINAL',0,900000,900000,1000000,900000,
                  'hybrid.project.v1')
            """, (run_id, project, candidate_id))
            reject(db, lambda: db.execute("""
                INSERT INTO plm.rag_context_bundles(
                  retrieval_run_id,project_id,context_policy_ref,
                  bundle_fingerprint,item_count,token_budget,token_count)
                VALUES (%s,%s,'project-documents.v1',sha256('bundle'::bytea),1,100,10)
            """, (run_id, project)), "ContextBundle Owner is not installed")
            assert db.execute(
                "SELECT count(*) FROM plm.rag_retrieval_candidates "
                "WHERE retrieval_run_id=%s", (run_id,),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.rag_retrieval_score_parts "
                "WHERE retrieval_run_id=%s", (run_id,),
            ).fetchone()[0] == 1

    activation_fixture.send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


def main() -> None:
    verify_empty_and_existing_upgrade()
    verify_history_refuses_downgrade()
    verify_bound_run_candidate_and_closed_context()
    print(
        "RAG_04_A02_P01_RETRIEVAL_SCHEMA_PASS: Schema0088 empty/existing "
        "upgrade, downgrade/re-upgrade, drift, ciphertext-only shape and "
        "retained-history refusal verified on PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
