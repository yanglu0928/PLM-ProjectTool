"""PostgreSQL owner for expired RAG Build/Index/Batch reconciliation."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow, JobLeaseRow, JobRow
from plm_assistant.modules.rag.application.reconcile_expired_build import (
    ReconciledRAGEmbeddingBuildFailure,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
    EmbeddingIndexRow,
)


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise RuntimeError("invalid RAG build reference")
    parsed = uuid.UUID(value)
    if not parsed.int or str(parsed) != value:
        raise RuntimeError("invalid RAG build reference")
    return parsed


class SqlAlchemyExpiredRAGEmbeddingBuildReconciliationRepository:
    def reconcile_next(
        self, transaction: object,
    ) -> ReconciledRAGEmbeddingBuildFailure | None:
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(JobRow).where(
            JobRow.owner_module == "rag",
            JobRow.job_type == "RAG_INDEX_BUILD",
            JobRow.state == "RUNNING",
            JobRow.lease_expires_at.is_not(None),
            JobRow.lease_expires_at <= now,
        ).order_by(JobRow.lease_expires_at, JobRow.job_id).limit(1)
            .with_for_update(of=JobRow, skip_locked=True)
            .execution_options(populate_existing=True))
        if job is None:
            return None
        payload = job.payload_refs
        if (type(payload) is not dict
                or set(payload) != {
                    "embedding_build_id", "embedding_index_id", "build_generation",
                }
                or payload["build_generation"] != 1):
            raise RuntimeError("inconsistent expired RAG build Job")
        build_id = _uuid(payload["embedding_build_id"])
        index_id = _uuid(payload["embedding_index_id"])
        lease = session.scalar(select(JobLeaseRow).where(
            JobLeaseRow.job_id == job.job_id,
            JobLeaseRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobLeaseRow).execution_options(populate_existing=True))
        attempt = session.scalar(select(JobAttemptRow).where(
            JobAttemptRow.job_id == job.job_id,
            JobAttemptRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
        build = session.scalar(select(EmbeddingBuildRow).where(
            EmbeddingBuildRow.embedding_build_id == build_id,
        ).with_for_update(of=EmbeddingBuildRow).execution_options(populate_existing=True))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(populate_existing=True))
        batches = list(session.scalars(select(EmbeddingBuildBatchRow).where(
            EmbeddingBuildBatchRow.embedding_build_id == build_id,
        ).order_by(EmbeddingBuildBatchRow.batch_ordinal)
            .with_for_update(of=EmbeddingBuildBatchRow)
            .execution_options(populate_existing=True)))
        if (lease is None or attempt is None or build is None or index is None
                or type(job.actor_ref) is not uuid.UUID or not job.actor_ref.int
                or job.max_attempts != 1 or job.attempt_count != 1
                or job.fencing_token != 1 or job.completed_at is not None
                or job.lease_expires_at is None
                or job.lease_expires_at != lease.lease_expires_at
                or lease.state != "ACTIVE" or lease.lease_expires_at > now
                or attempt.attempt_no != 1
                or attempt.fencing_token != lease.fencing_token
                or attempt.worker_ref != lease.worker_ref
                or attempt.completed_at is not None or attempt.error_code is not None
                or build.embedding_index_id != index_id
                or build.build_job_ref != job.job_id
                or build.build_generation != 1
                or build.build_state != "RUNNING" or build.lock_version != 1
                or index.index_state != "BUILDING" or index.lock_version != 1
                or build.scope != job.scope or build.project_id != job.project_id
                or index.scope != job.scope or index.project_id != job.project_id
                or build.created_by != job.actor_ref
                or job.trace_id == ""
                or job.idempotency_key != f"rag-index-build:{index_id}:1"
                or len(batches) != build.batch_count
                or [row.batch_ordinal for row in batches]
                   != list(range(1, build.batch_count + 1))
                or any(row.batch_state not in {
                    "PENDING", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN", "CANCELLED",
                } for row in batches)):
            raise RuntimeError("inconsistent expired RAG build generation")
        trace_id = _uuid(job.trace_id)
        running_count = sum(row.batch_state == "RUNNING" for row in batches)
        error_code = (
            "RAG_PROVIDER_OUTCOME_UNKNOWN" if running_count
            else "RAG_BUILD_LEASE_EXPIRED"
        )
        lease.state = "EXPIRED"
        attempt.completed_at = now
        attempt.error_code = error_code
        job.state = "FAILED"
        job.lease_expires_at = None
        job.completed_at = now
        session.flush()
        for batch in batches:
            if batch.batch_state == "PENDING":
                batch.batch_state = "CANCELLED"
                batch.error_code = "RAG_BUILD_LEASE_EXPIRED"
                batch.started_at = now
                batch.completed_at = now
                batch.lock_version += 1
            elif batch.batch_state == "RUNNING":
                batch.batch_state = "UNKNOWN"
                batch.error_code = "RAG_PROVIDER_OUTCOME_UNKNOWN"
                batch.completed_at = now
                batch.lock_version += 1
        session.flush()
        build.build_state = "FAILED"
        build.lock_version += 1
        session.flush()
        index.index_state = "FAILED"
        index.lock_version += 1
        session.flush()
        return ReconciledRAGEmbeddingBuildFailure(
            job.job_id, build.embedding_build_id, index.embedding_index_id,
            job.scope, job.project_id, job.actor_ref, trace_id,
            running_count, error_code, False, now,
        )
