"""Windows 11/PostgreSQL 18 proof for Retrieval Worker and RAG Context read."""

from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaims
from plm_assistant.modules.jobs.infrastructure.rag_retrieval_claim_repository import (
    SqlAlchemyRAGRetrievalClaimRepository,
)
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.rag.application.fts_retrieval_merge import FTSRetrievalMergePlanner
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalQueryPreparationService,
)
from plm_assistant.modules.rag.application.project_fts_candidates import ProjectFTSCandidatePlanner
from plm_assistant.modules.rag.application.retrieval_context import (
    RAGContextReadError,
    RAGContextReadRequest,
    RAGContextReadService,
)
from plm_assistant.modules.rag.application.retrieval_terminal import RAGRetrievalTerminalService
from plm_assistant.modules.rag.application.retrieval_worker import RAGRetrievalOneShotWorker
from plm_assistant.modules.rag.infrastructure.project_fts_candidate_repository import (
    SqlAlchemyProjectFTSCandidateRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_context_repository import (
    SqlAlchemyRAGContextRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_crypto import AesGcmRetrievalQueryCrypto
from plm_assistant.modules.rag.infrastructure.retrieval_query_preparation_repository import (
    SqlAlchemyRAGRetrievalQueryPreparationRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_terminal_repository import (
    SqlAlchemyRAGRetrievalTerminalRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


create_fixture = load(
    ROOT / "validation/rag-04-a02-p02-retrieval-create/verify.py",
    "rag_worker_create_fixture",
)
begin_fixture = create_fixture.begin_fixture


class FixedSystemActor:
    def __init__(self, actor_id): self.actor_id = actor_id
    def assert_current(self): return self.actor_id


def create_pending(database: str, *, actor, project, index_id, query: str,
                   cipher: AesGcmRetrievalQueryCrypto):
    run_id, job_id, trace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    normalized = query
    query_fingerprint = canonical_payload_fingerprint({
        "domain": "rag-query-v1", "query": normalized,
    })
    retention = datetime.now(timezone.utc) + timedelta(days=1)
    encrypted = cipher.encrypt(
        retrieval_run_id=run_id, project_id=project,
        query_fingerprint=query_fingerprint,
        plaintext=bytearray(normalized.encode("utf-8")),
        retention_until=retention,
    )
    filter_fingerprint = canonical_payload_fingerprint({})
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
                  rerank_state,egress_state,job_id,trace_id)
                VALUES (%s,'PROJECT',%s,%s,%s,'{}'::jsonb,%s,NULL,%s,
                  'fts.project.v1','none.v1',5,'NOT_APPLICABLE',
                  'NOT_APPLICABLE',%s,%s)
            """, (run_id, project, actor, query_fingerprint,
                    filter_fingerprint, index_id, job_id, trace_id))
            db.execute("""
                INSERT INTO plm.rag_retrieval_query_contents(
                  retrieval_run_id,project_id,query_fingerprint,
                  encrypted_payload,encryption_metadata,key_provider_ref,
                  plaintext_bytes,retention_until)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (run_id, project, query_fingerprint,
                    encrypted.encrypted_payload, Jsonb(encrypted.encryption_metadata),
                    encrypted.key_provider_ref, encrypted.plaintext_bytes,
                    encrypted.retention_until))
    return run_id, job_id


def context_size(database: str, run_id) -> tuple[uuid.UUID, bytes, int, int]:
    with begin_fixture.connect(database) as db:
        bundle_id, fingerprint, count = db.execute(
            "SELECT context_bundle_id,bundle_fingerprint,item_count FROM "
            "plm.rag_context_bundles WHERE retrieval_run_id=%s", (run_id,),
        ).fetchone()
        rows = db.execute("""
            SELECT item.item_ordinal,item.chunk_id,item.document_version_ref,
                   item.source_locator,chunk.search_body,
                   item.snippet_start,item.snippet_end
              FROM plm.rag_context_items item
              JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=item.chunk_id
             WHERE item.context_bundle_id=%s ORDER BY item.item_ordinal
        """, (bundle_id,)).fetchall()
    items = [{
        "document_version_id": str(row[2]), "node_id": str(row[1]),
        "ordinal": row[0], "source_locator": row[3],
        "text": row[4][row[5]:row[6]],
    } for row in rows]
    content = json.dumps({
        "context_bundle_id": str(bundle_id), "items": items,
        "retrieval_run_id": str(run_id),
        "schema_version": "rag-context-minimum-text.v1",
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
       allow_nan=False).encode("utf-8")
    return bundle_id, bytes(fingerprint), count, len(content)


def execute(context, envelope, sender, adapter) -> None:
    create_fixture.execute(context, envelope, sender, adapter, query_text="PLM")
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
    claims = RAGRetrievalClaims(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyRAGRetrievalClaimRepository(),
    )
    guard = create_fixture.activation_fixture.quality_fixture.Guard()
    keys = create_fixture.Keys()
    cipher = AesGcmRetrievalQueryCrypto(keys, key_ref="rag-query-proof.v1")
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    terminal = RAGRetrievalTerminalService(
        unit_of_work=runtime.unit_of_work, claims=claims,
        repository=SqlAlchemyRAGRetrievalTerminalRepository(),
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=FixedSystemActor(actor),
    )
    worker = RAGRetrievalOneShotWorker(
        claims=claims,
        preparation=RAGRetrievalQueryPreparationService(
            unit_of_work=runtime.unit_of_work, claims=claims,
            license_guard=guard, authorization=authorization,
            repository=SqlAlchemyRAGRetrievalQueryPreparationRepository(),
            cipher=cipher, clock=lambda: datetime.now(timezone.utc),
        ),
        candidates=ProjectFTSCandidatePlanner(
            SqlAlchemyProjectFTSCandidateRepository()),
        merge=FTSRetrievalMergePlanner(), terminal=terminal,
    )
    succeeded = worker.run_once(worker_ref="rag-retrieval-worker-a05")
    assert succeeded.state == "SUCCEEDED" and succeeded.candidate_count == 1
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE "
            "action='RAG_RETRIEVAL_COMPLETED' AND target_object_id=%s",
            (succeeded.retrieval_run_id,),
        ).fetchone()[0] == 1

    bundle_id, fingerprint, count, size = context_size(
        database, succeeded.retrieval_run_id)
    reader = RAGContextReadService(
        authorization=authorization, license_guard=guard,
        repository=SqlAlchemyRAGContextRepository(),
    )
    request = RAGContextReadRequest(
        project, actor, uuid.uuid4(), succeeded.retrieval_run_id,
        bundle_id, fingerprint, count, size,
    )
    with runtime.unit_of_work() as tx:
        projection = reader.read_exact(tx, request=request)
        assert b"PLM begin one" in projection.content_utf8
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='SUSPENDED' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
    try:
        with runtime.unit_of_work() as tx:
            reader.read_exact(tx, request=request)
    except RAGContextReadError as error:
        assert error.code == "RESOURCE_NOT_FOUND"
    else:
        raise AssertionError("revoked actor read RAG Context")

    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
    failed_run, _ = create_pending(
        database, actor=actor, project=project, index_id=index_id,
        query="no-match-token-7f6a19", cipher=cipher,
    )
    failed = worker.run_once(worker_ref="rag-retrieval-worker-a05")
    assert failed.state == "FAILED"
    assert failed.error_code == "RAG_NO_AUTHORIZED_CANDIDATES"
    assert failed.retrieval_run_id == failed_run

    expired_run, expired_job = create_pending(
        database, actor=actor, project=project, index_id=index_id,
        query="PLM", cipher=cipher,
    )
    expired_claim = claims.claim_next(
        worker_ref="rag-retrieval-expired-a05", lease_seconds=300,
    )
    assert expired_claim is not None and expired_claim.job_id == expired_job
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.job_leases SET lease_expires_at=acquired_at "
            "+ interval '1 microsecond' WHERE job_id=%s", (expired_job,),
        )
        db.execute(
            "UPDATE plm.job_jobs job SET lease_expires_at=lease.lease_expires_at "
            "FROM plm.job_leases lease WHERE job.job_id=lease.job_id "
            "AND job.job_id=%s", (expired_job,),
        )
    reconciled = terminal.reconcile_expired_next()
    assert reconciled is not None
    assert reconciled.retrieval_run_id == expired_run
    assert reconciled.error_code == "RAG_RETRIEVAL_LEASE_EXPIRED"
    with begin_fixture.connect(database) as db:
        rows = db.execute("""
            SELECT run.retrieval_state,job.state,lease.state,attempt.error_code,
              (SELECT count(*) FROM plm.rag_retrieval_candidates c
                WHERE c.retrieval_run_id=run.retrieval_run_id),
              (SELECT count(*) FROM plm.rag_context_bundles b
                WHERE b.retrieval_run_id=run.retrieval_run_id)
            FROM plm.rag_retrieval_runs run
            JOIN plm.job_jobs job ON job.job_id=run.job_id
            JOIN plm.job_leases lease ON lease.job_id=job.job_id
            JOIN plm.job_attempts attempt ON attempt.job_id=job.job_id
            WHERE run.retrieval_run_id IN (%s,%s)
            ORDER BY run.retrieval_run_id
        """, (failed_run, expired_run)).fetchall()
        assert {row[:4] for row in rows} == {
            ("FAILED", "FAILED", "RELEASED", "RAG_NO_AUTHORIZED_CANDIDATES"),
            ("FAILED", "FAILED", "EXPIRED", "RAG_RETRIEVAL_LEASE_EXPIRED"),
        }
        assert all(row[4:] == (0, 0) for row in rows)
    print(
        "RAG_04_A05_P02_RETRIEVAL_WORKER_CONTEXT_PASS: one-shot FTS success, "
        "known zero-candidate failure, expired reconciliation, atomic Audit and "
        "current-authority minimum AI Context read passed on Windows 11/PostgreSQL 18.6"
    )


def main() -> None:
    create_fixture.activation_fixture.send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
