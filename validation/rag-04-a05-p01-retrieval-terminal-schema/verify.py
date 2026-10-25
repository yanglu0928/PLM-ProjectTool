"""Windows 11/PostgreSQL 18 proof for Schema0089 atomic retrieval terminals."""

from __future__ import annotations

import importlib.util
import time
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg.types.json import Jsonb

from plm_assistant.modules.jobs.application.rag_retrieval_claim import (
    RAGRetrievalClaims,
)
from plm_assistant.modules.jobs.infrastructure.rag_retrieval_claim_repository import (
    SqlAlchemyRAGRetrievalClaimRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema_fixture = load(
    ROOT / "validation/rag-04-a02-p01-retrieval-schema/verify.py",
    "rag_terminal_schema_fixture",
)
create_fixture = load(
    ROOT / "validation/rag-04-a02-p02-retrieval-create/verify.py",
    "rag_terminal_create_fixture",
)
begin_fixture = create_fixture.begin_fixture


def reject(db, operation, expected: str) -> None:
    try:
        with db.transaction():
            operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"database operation unexpectedly succeeded: {expected}")


def verify_migration_cycle() -> None:
    database = schema_fixture.create_database("rag04a05p01mig_")
    try:
        cfg = schema_fixture.config(database)
        command.upgrade(cfg, "20261004_0088")
        actor = uuid.uuid4()
        with schema_fixture.connect(database) as db:
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized,state,deployment_role) "
                "VALUES (%s,'0089 existing actor','0089-existing-actor',"
                "'DISABLED','NONE')", (actor,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with schema_fixture.connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (actor,),
            ).fetchone()[0] == 1
            constraint = db.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE connamespace='plm'::regnamespace AND "
                "conname='ck_rag_retrieval_runs__lifecycle'"
            ).fetchone()
            assert constraint is not None and "SUCCEEDED" in constraint[0]
        command.downgrade(cfg, "20261004_0088")
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        schema_fixture.drop_database(database)


def create_pending_run(database: str, *, actor: uuid.UUID, project: uuid.UUID,
                       index_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    run_id, job_id, trace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with begin_fixture.connect(database) as db:
        with db.transaction():
            db.execute("""
                INSERT INTO plm.job_jobs(
                  job_id,owner_module,job_type,scope,project_id,actor_ref,
                  trace_id,payload_refs,idempotency_key,max_attempts)
                VALUES (%s,'rag','RAG_RETRIEVAL','PROJECT',%s,%s,%s,
                  jsonb_build_object('retrieval_run_id',%s::text),%s,1)
            """, (job_id, project, actor, str(trace_id), run_id, str(run_id)))
            db.execute("""
                INSERT INTO plm.rag_retrieval_runs(
                  retrieval_run_id,scope,project_id,actor_ref,query_fingerprint,
                  metadata_filter,metadata_filter_fingerprint,global_index_ref,
                  project_index_ref,retrieval_policy_ref,rerank_policy_ref,top_k,
                  rerank_state,egress_state,retrieval_state,quality_flags,
                  degraded,error_code,job_id,trace_id)
                VALUES (%s,'PROJECT',%s,%s,sha256('PLM'::bytea),'{}'::jsonb,
                  sha256('{}'::bytea),NULL,%s,'fts.project.v1','none.v1',5,
                  'NOT_APPLICABLE','NOT_APPLICABLE','RUNNING','[]'::jsonb,
                  false,NULL,%s,%s)
            """, (run_id, project, actor, index_id, job_id, trace_id))
            db.execute("""
                INSERT INTO plm.rag_retrieval_query_contents(
                  retrieval_run_id,project_id,query_fingerprint,
                  encrypted_payload,encryption_metadata,key_provider_ref,
                  plaintext_bytes,retention_until)
                VALUES (%s,%s,sha256('PLM'::bytea),%s,
                  '{"format":"rag-query-aesgcm.v1","nonce":"synthetic"}'::jsonb,
                  'synthetic-key.v1',3,statement_timestamp()+interval '1 day')
            """, (run_id, project, b"c" * 32))
    return run_id, job_id


def claim(runtime, *, lease_seconds: int):
    claims = RAGRetrievalClaims(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyRAGRetrievalClaimRepository(),
    )
    result = claims.claim_next(
        worker_ref="rag-terminal-schema-worker", lease_seconds=lease_seconds,
    )
    assert result is not None
    return result


def candidate_insert(db, *, run_id: uuid.UUID, project: uuid.UUID,
                     index_id: uuid.UUID):
    return db.execute("""
        INSERT INTO plm.rag_retrieval_candidates(
          retrieval_run_id,run_project_id,candidate_scope,
          candidate_project_id,embedding_index_id,embedding_model_ref,
          chunk_id,document_version_ref,parse_result_ref,source_type,
          source_locator,retrieval_channel,candidate_ordinal,
          final_score_micros,authorization_snapshot_fingerprint)
        SELECT %s,%s,'PROJECT',%s,index_row.embedding_index_id,
          index_row.embedding_model_ref,chunk.chunk_id,
          chunk.document_version_ref,chunk.parse_result_ref,
          chunk.source_type,chunk.source_locator,'FTS',0,900000,
          sha256('synthetic access snapshot'::bytea)
        FROM plm.rag_embedding_indexes index_row
        JOIN plm.rag_index_source_chunks source
          ON source.embedding_index_id=index_row.embedding_index_id
        JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
        WHERE index_row.embedding_index_id=%s
        ORDER BY source.source_ordinal LIMIT 1
        RETURNING candidate_id,chunk_id,document_version_ref,source_locator,
                  authorization_snapshot_fingerprint
    """, (run_id, project, project, index_id)).fetchone()


def close_job(db, *, run_id: uuid.UUID, job_id: uuid.UUID,
              completed_at, state: str, error_code: str | None,
              lease_state: str) -> None:
    db.execute(
        "UPDATE plm.job_leases SET state=%s WHERE job_id=%s AND fencing_token=1",
        (lease_state, job_id),
    )
    db.execute(
        "UPDATE plm.job_attempts SET completed_at=%s,error_code=%s "
        "WHERE job_id=%s AND fencing_token=1",
        (completed_at, error_code, job_id),
    )
    db.execute(
        "UPDATE plm.job_jobs SET state=%s,lease_expires_at=NULL,completed_at=%s "
        "WHERE job_id=%s", (state, completed_at, job_id),
    )
    db.execute(
        "UPDATE plm.rag_retrieval_runs SET retrieval_state=%s,"
        "rerank_state='NOT_APPLICABLE',egress_state='NOT_APPLICABLE',"
        "quality_flags=CASE WHEN %s='SUCCEEDED' "
        "THEN '[\"CANDIDATE_SHORTFALL\"]'::jsonb ELSE '[]'::jsonb END,"
        "error_code=%s,completed_at=%s,lock_version=1 "
        "WHERE retrieval_run_id=%s",
        (state, state, error_code, completed_at, run_id),
    )


def publish_success(database: str, *, claim, project: uuid.UUID,
                    index_id: uuid.UUID) -> None:
    with begin_fixture.connect(database) as db:
        with db.transaction():
            completed_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
            candidate = candidate_insert(
                db, run_id=claim.retrieval_run_id, project=project,
                index_id=index_id,
            )
            candidate_id, chunk_id, version_id, locator, access = candidate
            db.execute("""
                INSERT INTO plm.rag_retrieval_score_parts(
                  retrieval_run_id,project_id,candidate_id,score_kind,
                  score_ordinal,raw_score_micros,normalized_score_micros,
                  weight_micros,weighted_score_micros,score_policy_ref)
                VALUES
                  (%s,%s,%s,'FTS',0,900000,900000,1000000,900000,
                   'fts.project.v1'),
                  (%s,%s,%s,'FINAL',1,900000,900000,1000000,900000,
                   'fts.project.v1')
            """, (claim.retrieval_run_id, project, candidate_id,
                    claim.retrieval_run_id, project, candidate_id))
            close_job(
                db, run_id=claim.retrieval_run_id, job_id=claim.job_id,
                completed_at=completed_at, state="SUCCEEDED", error_code=None,
                lease_state="RELEASED",
            )
            bundle_id = db.execute("""
                INSERT INTO plm.rag_context_bundles(
                  retrieval_run_id,project_id,context_policy_ref,
                  bundle_fingerprint,item_count,token_budget,token_count)
                VALUES (%s,%s,'project-documents.v1',
                  sha256(convert_to(%s,'UTF8')),1,128,1)
                RETURNING context_bundle_id
            """, (claim.retrieval_run_id, project,
                    str(claim.retrieval_run_id))).fetchone()[0]
            db.execute("""
                INSERT INTO plm.rag_context_items(
                  context_bundle_id,retrieval_run_id,project_id,candidate_id,
                  item_ordinal,chunk_id,document_version_ref,source_locator,
                  snippet_start,snippet_end,token_count,snippet_fingerprint,
                  access_snapshot_fingerprint)
                VALUES (%s,%s,%s,%s,0,%s,%s,%s,0,3,1,
                  sha256('PLM'::bytea),%s)
            """, (bundle_id, claim.retrieval_run_id, project, candidate_id,
                    chunk_id, version_id, Jsonb(locator), access))
        assert db.execute(
            "SELECT run.retrieval_state,job.state,run.quality_flags,"
            "(SELECT count(*) FROM plm.rag_retrieval_candidates candidate "
            " WHERE candidate.retrieval_run_id=run.retrieval_run_id),"
            "(SELECT count(*) FROM plm.rag_retrieval_score_parts score "
            " WHERE score.retrieval_run_id=run.retrieval_run_id),"
            "(SELECT count(*) FROM plm.rag_context_items item "
            " WHERE item.retrieval_run_id=run.retrieval_run_id) "
            "FROM plm.rag_retrieval_runs run JOIN plm.job_jobs job "
            "ON job.job_id=run.job_id WHERE run.retrieval_run_id=%s",
            (claim.retrieval_run_id,),
        ).fetchone() == (
            "SUCCEEDED", "SUCCEEDED", ["CANDIDATE_SHORTFALL"], 1, 2, 1,
        )


def verify_atomic_paths(context, envelope, sender, adapter) -> None:
    create_fixture.execute(
        context, envelope, sender, adapter, query_text="PLM",
    )
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )

    success = claim(runtime, lease_seconds=30)
    publish_success(database, claim=success, project=project, index_id=index_id)

    failed_run, failed_job = create_pending_run(
        database, actor=actor, project=project, index_id=index_id,
    )
    failed = claim(runtime, lease_seconds=30)
    assert (failed.retrieval_run_id, failed.job_id) == (failed_run, failed_job)
    with begin_fixture.connect(database) as db:
        with db.transaction():
            completed_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
            close_job(
                db, run_id=failed_run, job_id=failed_job,
                completed_at=completed_at, state="FAILED",
                error_code="RAG_NO_AUTHORIZED_CANDIDATES",
                lease_state="RELEASED",
            )

    expired_run, expired_job = create_pending_run(
        database, actor=actor, project=project, index_id=index_id,
    )
    expired = claim(runtime, lease_seconds=3)
    assert (expired.retrieval_run_id, expired.job_id) == (expired_run, expired_job)
    time.sleep(4)
    with begin_fixture.connect(database) as db:
        with db.transaction():
            completed_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
            close_job(
                db, run_id=expired_run, job_id=expired_job,
                completed_at=completed_at, state="FAILED",
                error_code="RAG_RETRIEVAL_LEASE_EXPIRED",
                lease_state="EXPIRED",
            )

    partial_run, partial_job = create_pending_run(
        database, actor=actor, project=project, index_id=index_id,
    )
    partial = claim(runtime, lease_seconds=30)
    assert (partial.retrieval_run_id, partial.job_id) == (partial_run, partial_job)
    with begin_fixture.connect(database) as db:
        reject(
            db,
            lambda: candidate_insert(
                db, run_id=partial_run, project=project, index_id=index_id,
            ),
            "cannot commit before terminal state",
        )

        def success_without_context():
            completed_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
            candidate_id = candidate_insert(
                db, run_id=partial_run, project=project, index_id=index_id,
            )[0]
            db.execute("""
                INSERT INTO plm.rag_retrieval_score_parts(
                  retrieval_run_id,project_id,candidate_id,score_kind,
                  score_ordinal,raw_score_micros,normalized_score_micros,
                  weight_micros,weighted_score_micros,score_policy_ref)
                VALUES
                  (%s,%s,%s,'FTS',0,900000,900000,1000000,900000,
                   'fts.project.v1'),
                  (%s,%s,%s,'FINAL',1,900000,900000,1000000,900000,
                   'fts.project.v1')
            """, (partial_run, project, candidate_id,
                    partial_run, project, candidate_id))
            close_job(
                db, run_id=partial_run, job_id=partial_job,
                completed_at=completed_at, state="SUCCEEDED", error_code=None,
                lease_state="RELEASED",
            )

        reject(
            db, success_without_context,
            "success terminal transaction is incomplete",
        )
        assert db.execute(
            "SELECT count(*) FROM plm.rag_retrieval_candidates "
            "WHERE retrieval_run_id=%s", (partial_run,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT run.retrieval_state,job.state,lease.state,"
            "attempt.completed_at IS NULL FROM plm.rag_retrieval_runs run "
            "JOIN plm.job_jobs job ON job.job_id=run.job_id "
            "JOIN plm.job_leases lease ON lease.job_id=job.job_id "
            "JOIN plm.job_attempts attempt ON attempt.job_id=job.job_id "
            "WHERE run.retrieval_run_id=%s", (partial_run,),
        ).fetchone() == ("RUNNING", "RUNNING", "ACTIVE", True)
        terminal = db.execute("""
            SELECT run.retrieval_state,job.state,attempt.error_code,lease.state,
              (SELECT count(*) FROM plm.rag_retrieval_candidates candidate
                WHERE candidate.retrieval_run_id=run.retrieval_run_id),
              (SELECT count(*) FROM plm.rag_context_bundles bundle
                WHERE bundle.retrieval_run_id=run.retrieval_run_id)
            FROM plm.rag_retrieval_runs run
            JOIN plm.job_jobs job ON job.job_id=run.job_id
            JOIN plm.job_attempts attempt ON attempt.job_id=job.job_id
            JOIN plm.job_leases lease ON lease.job_id=job.job_id
            WHERE run.retrieval_run_id IN (%s,%s)
            ORDER BY run.retrieval_run_id
        """, (failed_run, expired_run)).fetchall()
        assert {row[:4] for row in terminal} == {
            ("FAILED", "FAILED", "RAG_NO_AUTHORIZED_CANDIDATES", "RELEASED"),
            ("FAILED", "FAILED", "RAG_RETRIEVAL_LEASE_EXPIRED", "EXPIRED"),
        }
        assert all(row[4:] == (0, 0) for row in terminal)

    try:
        command.downgrade(schema_fixture.config(database), "20261004_0088")
    except Exception as error:
        assert "terminal RAG Retrieval history prevents downgrade" in str(error)
    else:
        raise AssertionError("Schema0089 downgrade accepted terminal history")


def main() -> None:
    verify_migration_cycle()
    create_fixture.activation_fixture.send_fixture.main(
        execute=verify_atomic_paths, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )
    print(
        "RAG_04_A05_P01_RETRIEVAL_TERMINAL_SCHEMA_PASS: Schema0089 migration, "
        "drift, success/failure/expired atomic terminals, partial-result rollback "
        "and retained-history downgrade refusal passed on Windows 11/PostgreSQL 18.6"
    )


if __name__ == "__main__":
    main()
