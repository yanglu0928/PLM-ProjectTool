"""Windows 11/PostgreSQL 18 proof for authorized plan, owner claim and atomic begin."""

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

from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.application.rag_index_build_claim import RAGIndexBuildClaims
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.rag_index_build_claim_repository import (
    SqlAlchemyRAGIndexBuildClaimRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.rag.application.embedding_build_begin import (
    RAGEmbeddingBuildBeginService,
)
from plm_assistant.modules.rag.application.embedding_build_plan import (
    RAGEmbeddingBatchPlan,
    RAGEmbeddingBuildPlanRequest,
    RAGEmbeddingBuildPlanner,
)
from plm_assistant.modules.rag.infrastructure.embedding_build_begin_repository import (
    SqlAlchemyRAGEmbeddingBuildBeginRepository,
)
from plm_assistant.modules.rag.infrastructure.embedding_build_plan_repository import (
    SqlAlchemyRAGEmbeddingBuildPlanRepository,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/rag-03-a03-p01-build-plan-schema/verify.py",
    "rag_build_begin_fixture",
)


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject(operation, expected: str) -> None:
    try:
        operation()
    except Exception as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"operation unexpectedly succeeded: {expected}")


def main(after_begin=None, batch_payload_factory=None) -> None:
    database = "rag03a03p02_" + uuid.uuid4().hex[:10]
    scratch = Path(tempfile.mkdtemp(prefix="plm-rag03a03p02-"))
    runtime = None
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            url = URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT,
                database=database,
            )
            config = create_migration_config(url)
            command.upgrade(config, "20261004_0078")
            storage = LocalParseResultStorage(scratch)
            with connect(database) as db:
                source = fixture.index_fixture.chunk_fixture.seed_source(db, storage)
                actor, project, _, _, version, record, result = source
                members = []
                for ordinal, body in enumerate(("PLM begin one", "PLM begin two"), 1):
                    chunk_id = db.execute(
                        fixture.index_fixture.chunk_fixture.CHUNK_INSERT,
                        fixture.index_fixture.chunk_fixture.chunk_values(
                            actor, project, version, record, result, ordinal - 1, body,
                        ),
                    ).fetchone()[0]
                    members.append((
                        ordinal, chunk_id, hashlib.sha256(body.encode("utf-8")).digest(),
                    ))
                model, _, _ = fixture.index_fixture.seed_provider_and_models(db, actor)
                index_id = fixture.index_fixture.create_index(
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
            batches = []
            with connect(database) as db:
                for ordinal, member in enumerate(members, 1):
                    source_fingerprint = fixture.batch_source_fingerprint(member)
                    if batch_payload_factory is None:
                        payload_fingerprint = hashlib.sha256(
                            f"begin-payload:{ordinal}".encode("utf-8")
                        ).digest()
                        payload_bytes, input_tokens = 200 + ordinal, 30 + ordinal
                    else:
                        payload_fingerprint, payload_bytes, input_tokens = (
                            batch_payload_factory(ordinal, member)
                        )
                    authorization = fixture.authorize_batch(
                        db, actor=actor, project=project, provider=provider,
                        provider_config=provider_config, model=model, index_id=index_id,
                        source_fingerprint=source_fingerprint,
                        payload_fingerprint=payload_fingerprint,
                        payload_bytes=payload_bytes, input_tokens=input_tokens,
                    )
                    batches.append(RAGEmbeddingBatchPlan(
                        ordinal, ordinal, 1, source_fingerprint,
                        payload_fingerprint, payload_bytes, input_tokens,
                        authorization,
                    ))
            runtime = create_database_runtime(url)
            planned = RAGEmbeddingBuildPlanner(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyRAGEmbeddingBuildPlanRepository(),
            ).create(RAGEmbeddingBuildPlanRequest(
                index_id, actor, uuid.uuid4(), tuple(batches),
            ))
            generic = JobLeaseService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyJobLeaseRepository(),
            )
            parser_claim = generic.claim_next_parse(
                worker_ref="parser-must-not-steal-rag", lease_seconds=60,
            )
            assert parser_claim is None or parser_claim.job_id != planned.job_id
            ai_claim = generic.claim_next_ai_task(
                worker_ref="ai-must-not-steal-rag", lease_seconds=60,
            )
            assert ai_claim is None or ai_claim.job_id != planned.job_id
            claims = RAGIndexBuildClaims(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyRAGIndexBuildClaimRepository(),
            )
            claim = claims.claim_next(worker_ref="rag-worker-01", lease_seconds=120)
            assert claim is not None
            assert claim.job_id == planned.job_id
            assert claim.embedding_build_id == planned.embedding_build_id
            assert claim.embedding_index_id == index_id
            begun = RAGEmbeddingBuildBeginService(
                unit_of_work=runtime.unit_of_work,
                claims=claims,
                repository=SqlAlchemyRAGEmbeddingBuildBeginRepository(),
            ).begin(
                job_id=claim.job_id, fencing_token=claim.fencing_token,
                worker_ref="rag-worker-01",
            )
            assert begun.embedding_build_id == planned.embedding_build_id
            with connect(database) as db:
                assert db.execute(
                    "SELECT build_state,lock_version FROM plm.rag_embedding_builds "
                    "WHERE embedding_build_id=%s", (planned.embedding_build_id,),
                ).fetchone() == ("RUNNING", 1)
                assert db.execute(
                    "SELECT index_state,lock_version FROM plm.rag_embedding_indexes "
                    "WHERE embedding_index_id=%s", (index_id,),
                ).fetchone() == ("BUILDING", 1)
                assert db.execute(
                    "SELECT state,attempt_count,max_attempts,fencing_token "
                    "FROM plm.job_jobs WHERE job_id=%s", (planned.job_id,),
                ).fetchone() == ("RUNNING", 1, 1, 1)
                assert db.execute(
                    "SELECT array_agg(batch_state ORDER BY batch_ordinal) "
                    "FROM plm.rag_embedding_build_batches WHERE embedding_build_id=%s",
                    (planned.embedding_build_id,),
                ).fetchone()[0] == ["PENDING", "PENDING"]
                reject(lambda: db.execute(
                    "INSERT INTO plm.rag_embedding_records(scope,project_id,"
                    "embedding_index_id,chunk_id,embedding_model_ref,embedding_dimension,"
                    "chunk_text_fingerprint,embedding_vector,vector_fingerprint,"
                    "egress_authorization_ref) VALUES "
                    "('PROJECT',%s,%s,%s,%s,1024,%s,'[0,0]'::vector,%s,%s)",
                    (project, index_id, members[0][1], model, members[0][2],
                     b"v" * 32, batches[0].egress_authorization_ref),
                ), "lacks a successful authorized Build batch")
                reject(lambda: db.execute(
                    "UPDATE plm.rag_embedding_build_batches SET batch_state='RUNNING',"
                    "send_fencing_token=2,started_at=statement_timestamp(),lock_version=1 "
                    "WHERE embedding_build_id=%s AND batch_ordinal=1",
                    (planned.embedding_build_id,),
                ), "invalid")
            assert claims.claim_next(
                worker_ref="rag-worker-02", lease_seconds=120,
            ) is None
            if after_begin is not None:
                after_begin({
                    "database": database,
                    "config": config,
                    "runtime": runtime,
                    "planned": planned,
                    "claim": claim,
                    "claims": claims,
                    "actor": actor,
                    "project": project,
                    "batches": tuple(batches),
                    "members": tuple(members),
                })
                return
            reject(lambda: command.downgrade(config, "20261004_0079"),
                   "started RAG EmbeddingBuild history prevents downgrade")
            print(
                "RAG_03_A03_P02_BUILD_BEGIN_PASS: Schema0080 migration/drift, "
                "authorized application plan creation, parser/AI owner isolation, "
                "single-attempt RAG claim, atomic Build RUNNING + Index BUILDING, "
                "current lease proof, PENDING-batch vector denial and started-history "
                "downgrade refusal verified on Windows 11/PostgreSQL 18"
            )
        finally:
            if runtime is not None:
                runtime.dispose()
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
