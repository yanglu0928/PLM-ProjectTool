"""PostgreSQL technical validation and atomic READY/FAILED convergence."""

from __future__ import annotations

import hashlib

from sqlalchemy import select, text

from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.rag.application.embedding_index_validation import (
    CompletedRAGEmbeddingIndexValidation,
    RAGEmbeddingIndexValidationPolicy,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildRow,
    EmbeddingIndexRow,
    EmbeddingIndexValidationRow,
)


_FAILURE_CODE = "RAG_INDEX_TECHNICAL_VALIDATION_FAILED"


class SqlAlchemyRAGEmbeddingIndexValidationRepository:
    def __init__(self) -> None:
        self._leases = SqlAlchemyJobLeaseRepository()

    def validate_and_close(
        self, transaction: object, *, claim: RAGIndexBuildClaim,
        worker_ref: str, policy: RAGEmbeddingIndexValidationPolicy,
    ) -> CompletedRAGEmbeddingIndexValidation:
        claim.__post_init__()
        policy.__post_init__()
        session = self._leases._session(transaction)
        build = session.scalar(select(EmbeddingBuildRow).where(
            EmbeddingBuildRow.embedding_build_id == claim.embedding_build_id,
            EmbeddingBuildRow.embedding_index_id == claim.embedding_index_id,
            EmbeddingBuildRow.build_job_ref == claim.job_id,
        ).with_for_update(of=EmbeddingBuildRow).execution_options(autoflush=False))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == claim.embedding_index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(autoflush=False))
        if not self._current(build, index, claim):
            raise RuntimeError("RAG index is not technically validatable")

        facts = self._facts(session, claim)
        if (facts["source_count"] != build.source_chunk_count
                or facts["expected_batch_count"] != build.batch_count
                or facts["available_count"] < 1):
            raise RuntimeError("RAG index build is incomplete")
        probe = self._probe(session, claim, build.embedding_dimension,
                            facts["available_count"], policy)
        passed = bool(
            facts["available_count"] == facts["source_count"]
            and facts["missing_count"] == 0
            and facts["extra_count"] == 0
            and facts["duplicate_count"] == 0
            and facts["invalid_count"] == 0
            and facts["succeeded_batch_count"]
            == facts["expected_batch_count"]
            and probe["hnsw_catalog_fingerprint"] is not None
            and probe["hnsw_plan_observed"]
            and probe["exact_plan_observed"]
            and probe["observed_recall_basis_points"]
            >= policy.minimum_recall_basis_points
        )
        validation_state = "PASSED" if passed else "FAILED"
        validation_fingerprint = hashlib.sha256(
            b"rag-index-technical-v1\0"
            + facts["record_set_fingerprint"]
            + (probe["hnsw_catalog_fingerprint"] or b"")
            + probe["plan_fingerprint"]
        ).digest()
        validation = EmbeddingIndexValidationRow(
            embedding_index_id=claim.embedding_index_id,
            embedding_build_id=claim.embedding_build_id,
            scope=claim.scope, project_id=claim.project_id,
            embedding_model_ref=build.embedding_model_ref,
            embedding_dimension=build.embedding_dimension,
            source_chunk_count=facts["source_count"],
            available_record_count=facts["available_count"],
            missing_record_count=facts["missing_count"],
            extra_record_count=facts["extra_count"],
            duplicate_record_count=facts["duplicate_count"],
            invalid_record_count=facts["invalid_count"],
            expected_batch_count=facts["expected_batch_count"],
            succeeded_batch_count=facts["succeeded_batch_count"],
            source_snapshot_fingerprint=build.source_snapshot_fingerprint,
            build_fingerprint=build.build_fingerprint,
            record_set_fingerprint=facts["record_set_fingerprint"],
            validation_policy_ref=policy.policy_ref,
            hnsw_index_name=probe["hnsw_index_name"],
            hnsw_catalog_fingerprint=probe["hnsw_catalog_fingerprint"],
            hnsw_plan_observed=probe["hnsw_plan_observed"],
            exact_plan_observed=probe["exact_plan_observed"],
            hnsw_ef_search=policy.hnsw_ef_search,
            hnsw_iterative_scan=policy.hnsw_iterative_scan,
            exact_query_count=probe["query_count"],
            exact_top_k=probe["top_k"],
            exact_overlap_count=probe["overlap_count"],
            exact_expected_count=probe["expected_count"],
            minimum_recall_basis_points=policy.minimum_recall_basis_points,
            observed_recall_basis_points=probe[
                "observed_recall_basis_points"
            ],
            plan_fingerprint=probe["plan_fingerprint"],
            validation_fingerprint=validation_fingerprint,
            validation_state=validation_state,
            error_code=None if passed else _FAILURE_CODE,
            validated_by=claim.actor_id,
        )
        session.add(validation)
        session.flush()

        if passed:
            self._leases.finish(
                transaction, job_id=claim.job_id,
                fencing_token=claim.fencing_token, worker_ref=worker_ref,
            )
            index_state = "READY"
            build_state = "SUCCEEDED"
        else:
            state = self._leases.retry_or_fail(
                transaction, job_id=claim.job_id,
                fencing_token=claim.fencing_token, worker_ref=worker_ref,
                error_code=_FAILURE_CODE, retryable=False, delay_seconds=0,
            )
            if state != "FAILED":
                raise RuntimeError("RAG validation failure did not close Job")
            index_state = build_state = "FAILED"

        build.build_state = build_state
        build.lock_version += 1
        session.flush()
        index.index_state = index_state
        index.lock_version += 1
        session.flush()
        job = session.get(JobRow, claim.job_id, populate_existing=True)
        if (job is None or job.completed_at is None
                or validation.embedding_index_validation_id is None):
            raise RuntimeError("RAG validation close result is incomplete")
        return CompletedRAGEmbeddingIndexValidation(
            validation.embedding_index_validation_id,
            claim.embedding_index_id, claim.embedding_build_id,
            validation_state, index_state,
            probe["observed_recall_basis_points"], job.completed_at,
        )

    @staticmethod
    def _current(build, index, claim: RAGIndexBuildClaim) -> bool:
        return bool(
            build is not None and index is not None
            and build.build_state == "RUNNING" and build.lock_version == 1
            and index.index_state == "BUILDING" and index.lock_version == 1
            and build.build_generation == claim.build_generation == 1
            and build.created_by == claim.actor_id
            and (build.scope, build.project_id)
            == (claim.scope, claim.project_id)
            and (index.scope, index.project_id)
            == (claim.scope, claim.project_id)
            and build.embedding_model_ref == index.embedding_model_ref
            and build.embedding_dimension == index.embedding_dimension
            and build.source_chunk_count == index.source_chunk_count
            and build.source_snapshot_fingerprint
            == index.source_snapshot_fingerprint
        )

    @staticmethod
    def _facts(session, claim: RAGIndexBuildClaim) -> dict[str, object]:
        params = {"index_id": claim.embedding_index_id,
                  "build_id": claim.embedding_build_id}
        row = session.execute(text("""
            SELECT
              (SELECT count(*) FROM plm.rag_index_source_chunks
                WHERE embedding_index_id=:index_id) AS source_count,
              (SELECT count(*) FROM plm.rag_embedding_records
                WHERE embedding_index_id=:index_id
                  AND embedding_state='AVAILABLE') AS available_count,
              (SELECT count(*) FROM plm.rag_index_source_chunks source
                WHERE source.embedding_index_id=:index_id AND NOT EXISTS (
                  SELECT 1 FROM plm.rag_embedding_records record
                   WHERE record.embedding_index_id=source.embedding_index_id
                     AND record.chunk_id=source.chunk_id
                     AND record.embedding_state='AVAILABLE')) AS missing_count,
              (SELECT count(*) FROM plm.rag_embedding_records record
                WHERE record.embedding_index_id=:index_id
                  AND record.embedding_state='AVAILABLE' AND NOT EXISTS (
                  SELECT 1 FROM plm.rag_index_source_chunks source
                   WHERE source.embedding_index_id=record.embedding_index_id
                     AND source.chunk_id=record.chunk_id)) AS extra_count,
              (SELECT coalesce(sum(n-1),0) FROM (
                  SELECT count(*) n FROM plm.rag_embedding_records
                   WHERE embedding_index_id=:index_id
                     AND embedding_state='AVAILABLE'
                   GROUP BY chunk_id HAVING count(*)>1) duplicate_groups
              ) AS duplicate_count,
              (SELECT count(*) FROM plm.rag_embedding_records
                WHERE embedding_index_id=:index_id
                  AND embedding_state<>'AVAILABLE') AS invalid_count,
              (SELECT count(*) FROM plm.rag_embedding_build_batches
                WHERE embedding_build_id=:build_id) AS expected_batch_count,
              (SELECT count(*) FROM plm.rag_embedding_build_batches
                WHERE embedding_build_id=:build_id
                  AND batch_state='SUCCEEDED') AS succeeded_batch_count,
              (SELECT sha256(convert_to(coalesce(string_agg(
                  source.source_ordinal::text || ':' || record.chunk_id::text ||
                  ':' || encode(record.vector_fingerprint,'hex'), E'\n'
                  ORDER BY source.source_ordinal),''),'UTF8'))
                 FROM plm.rag_index_source_chunks source
                 JOIN plm.rag_embedding_records record
                   ON record.embedding_index_id=source.embedding_index_id
                  AND record.chunk_id=source.chunk_id
                  AND record.embedding_state='AVAILABLE'
                WHERE source.embedding_index_id=:index_id
              ) AS record_set_fingerprint
        """), params).one()
        keys = (
            "source_count", "available_count", "missing_count", "extra_count",
            "duplicate_count", "invalid_count", "expected_batch_count",
            "succeeded_batch_count", "record_set_fingerprint",
        )
        return dict(zip(keys, row, strict=True))

    @staticmethod
    def _probe(session, claim: RAGIndexBuildClaim, dimension: int,
               available_count: int,
               policy: RAGEmbeddingIndexValidationPolicy) -> dict[str, object]:
        if dimension not in {768, 1024}:
            raise RuntimeError("unsupported RAG embedding dimension")
        top_k = min(policy.top_k, available_count)
        query_vectors = session.execute(text("""
            SELECT record.embedding_vector::text
              FROM plm.rag_index_source_chunks source
              JOIN plm.rag_embedding_records record
                ON record.embedding_index_id=source.embedding_index_id
               AND record.chunk_id=source.chunk_id
               AND record.embedding_state='AVAILABLE'
             WHERE source.embedding_index_id=:index_id
             ORDER BY source.source_ordinal LIMIT :probe_limit
        """), {"index_id": claim.embedding_index_id,
                 "probe_limit": policy.probe_limit}).scalars().all()
        if not query_vectors or top_k < 1:
            raise RuntimeError("RAG validation probe set is empty")

        hnsw_name = f"ix_rag_embeddings__v{dimension}_hnsw"
        indexdef = session.execute(text("""
            SELECT indexdef FROM pg_indexes WHERE schemaname='plm'
             AND tablename='rag_embedding_records' AND indexname=:index_name
        """), {"index_name": hnsw_name}).scalar_one_or_none()
        catalog_fingerprint = (
            hashlib.sha256(indexdef.encode("utf-8")).digest()
            if indexdef is not None else None
        )
        predicate = (
            "record.scope=:scope AND record.project_id IS NOT DISTINCT FROM "
            "CAST(:project_id AS uuid) AND record.embedding_index_id=:index_id "
            "AND record.embedding_state='AVAILABLE' AND "
            f"record.embedding_dimension={dimension} ORDER BY "
            f"record.embedding_vector::vector({dimension}) <=> "
            f"CAST(:query_vector AS vector({dimension})) LIMIT :top_k"
        )
        query = "SELECT record.embedding_record_id::text FROM " \
                "plm.rag_embedding_records record WHERE " + predicate
        explain = "EXPLAIN (COSTS OFF) " + query
        common = {"scope": claim.scope, "project_id": claim.project_id,
                  "index_id": claim.embedding_index_id, "top_k": top_k}
        hnsw_plans: list[str] = []
        exact_plans: list[str] = []
        overlap_count = 0
        expected_count = 0
        session.execute(text("SET LOCAL hnsw.ef_search = 200"))
        session.execute(text("SET LOCAL hnsw.iterative_scan = 'strict_order'"))
        for query_vector in query_vectors:
            params = {**common, "query_vector": query_vector}
            session.execute(text("SET LOCAL enable_seqscan = off"))
            session.execute(text("SET LOCAL enable_indexscan = on"))
            session.execute(text("SET LOCAL enable_bitmapscan = on"))
            session.execute(text("SET LOCAL enable_sort = off"))
            hnsw_plan = "\n".join(session.execute(
                text(explain), params,
            ).scalars())
            hnsw_rows = set(session.execute(text(query), params).scalars())
            session.execute(text("SET LOCAL enable_seqscan = on"))
            session.execute(text("SET LOCAL enable_indexscan = off"))
            session.execute(text("SET LOCAL enable_bitmapscan = off"))
            session.execute(text("SET LOCAL enable_sort = on"))
            exact_plan = "\n".join(session.execute(
                text(explain), params,
            ).scalars())
            exact_rows = set(session.execute(text(query), params).scalars())
            hnsw_plans.append(hnsw_plan)
            exact_plans.append(exact_plan)
            overlap_count += len(hnsw_rows & exact_rows)
            expected_count += len(exact_rows)
        session.execute(text("SET LOCAL enable_indexscan = on"))
        session.execute(text("SET LOCAL enable_bitmapscan = on"))
        plan_body = "\n---hnsw---\n".join(hnsw_plans)
        plan_body += "\n---exact---\n" + "\n---exact---\n".join(exact_plans)
        plan_fingerprint = hashlib.sha256(plan_body.encode("utf-8")).digest()
        recall = (overlap_count * 10000 // expected_count
                  if expected_count else 0)
        return {
            "hnsw_index_name": hnsw_name,
            "hnsw_catalog_fingerprint": catalog_fingerprint,
            "hnsw_plan_observed": bool(hnsw_plans) and all(
                hnsw_name in value for value in hnsw_plans),
            "exact_plan_observed": bool(exact_plans) and all(
                "Seq Scan" in value for value in exact_plans),
            "query_count": len(query_vectors), "top_k": top_k,
            "overlap_count": overlap_count, "expected_count": expected_count,
            "observed_recall_basis_points": recall,
            "plan_fingerprint": plan_fingerprint,
        }
