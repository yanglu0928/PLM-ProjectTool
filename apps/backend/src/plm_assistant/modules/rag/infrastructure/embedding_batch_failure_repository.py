"""PostgreSQL terminalization for one known Embedding batch failure."""

from __future__ import annotations

import hmac

from sqlalchemy import select

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import (
    JobAttemptRow,
    JobLeaseRow,
    JobRow,
)
from plm_assistant.modules.rag.application.embedding_batch_failure import (
    PublishedRAGEmbeddingBatchFailure,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
    EmbeddingIndexRow,
)


class SqlAlchemyRAGEmbeddingBatchFailureRepository:
    def publish(
        self, transaction: object, *, claim: RAGIndexBuildClaim,
        envelope: AIEmbeddingEnvelope, send: AuthorizedAIEmbeddingSend,
        error_code: str, response_ref: str | None,
    ) -> PublishedRAGEmbeddingBatchFailure | None:
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == claim.job_id,
        ).with_for_update(of=JobRow).execution_options(autoflush=False))
        lease = session.scalar(select(JobLeaseRow).where(
            JobLeaseRow.job_id == claim.job_id,
            JobLeaseRow.fencing_token == claim.fencing_token,
        ).with_for_update(of=JobLeaseRow).execution_options(autoflush=False))
        attempt = session.scalar(select(JobAttemptRow).where(
            JobAttemptRow.job_id == claim.job_id,
            JobAttemptRow.fencing_token == claim.fencing_token,
        ).with_for_update(of=JobAttemptRow).execution_options(autoflush=False))
        build = session.scalar(select(EmbeddingBuildRow).where(
            EmbeddingBuildRow.embedding_build_id == claim.embedding_build_id,
            EmbeddingBuildRow.embedding_index_id == claim.embedding_index_id,
            EmbeddingBuildRow.build_job_ref == claim.job_id,
        ).with_for_update(of=EmbeddingBuildRow).execution_options(autoflush=False))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == claim.embedding_index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(autoflush=False))
        batches = list(session.scalars(select(EmbeddingBuildBatchRow).where(
            EmbeddingBuildBatchRow.embedding_build_id
            == claim.embedding_build_id,
        ).order_by(EmbeddingBuildBatchRow.batch_ordinal)
            .with_for_update(of=EmbeddingBuildBatchRow)
            .execution_options(autoflush=False)))
        current = next((row for row in batches
                        if row.embedding_build_batch_id
                        == envelope.embedding_build_batch_id), None)
        if not self._current(
                job, lease, attempt, build, index, batches, current,
                claim, envelope, send, error_code, response_ref):
            return None
        completed_at = job.completed_at
        current.batch_state = "FAILED"
        current.provider_request_ref = response_ref
        current.error_code = error_code
        current.completed_at = completed_at
        current.lock_version += 1
        cancelled = 0
        for batch in batches:
            if batch.batch_state == "PENDING":
                batch.batch_state = "CANCELLED"
                batch.error_code = "RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE"
                batch.started_at = completed_at
                batch.completed_at = completed_at
                batch.lock_version += 1
                cancelled += 1
        session.flush()
        build.build_state = "FAILED"
        build.lock_version += 1
        session.flush()
        index.index_state = "FAILED"
        index.lock_version += 1
        session.flush()
        return PublishedRAGEmbeddingBatchFailure(
            current.embedding_build_batch_id, error_code,
            cancelled, completed_at,
        )

    @staticmethod
    def _current(
        job, lease, attempt, build, index, batches, current,
        claim: RAGIndexBuildClaim, envelope: AIEmbeddingEnvelope,
        send: AuthorizedAIEmbeddingSend, error_code: str,
        response_ref: str | None,
    ) -> bool:
        proof = send.proof
        if any(value is None for value in (
                job, lease, attempt, build, index, current)):
            return False
        expected_states = []
        for batch in batches:
            if batch.batch_ordinal < envelope.batch_ordinal:
                expected_states.append("SUCCEEDED")
            elif batch.batch_ordinal == envelope.batch_ordinal:
                expected_states.append("RUNNING")
            else:
                expected_states.append("PENDING")
        return bool(
            job.state == "FAILED" and job.max_attempts == 1
            and job.attempt_count == claim.attempt_no == 1
            and job.fencing_token == claim.fencing_token == 1
            and job.lease_expires_at is None and job.completed_at is not None
            and lease.state == "RELEASED"
            and lease.lease_expires_at >= job.completed_at
            and attempt.attempt_no == 1 and attempt.worker_ref == lease.worker_ref
            and attempt.completed_at == job.completed_at
            and attempt.error_code == error_code
            and build.build_state == "RUNNING" and build.lock_version == 1
            and build.build_generation == claim.build_generation == 1
            and build.created_by == claim.actor_id
            and (build.scope, build.project_id) == (claim.scope, claim.project_id)
            and index.index_state == "BUILDING" and index.lock_version == 1
            and (index.scope, index.project_id) == (claim.scope, claim.project_id)
            and len(batches) == build.batch_count
            and [row.batch_ordinal for row in batches]
            == list(range(1, build.batch_count + 1))
            and [row.batch_state for row in batches] == expected_states
            and current.batch_ordinal == envelope.batch_ordinal
            and current.batch_state == "RUNNING" and current.lock_version == 1
            and current.send_fencing_token == claim.fencing_token
            and current.provider_request_ref is None
            and current.error_code is None and current.started_at is not None
            and current.completed_at is None
            and current.source_first_ordinal == envelope.source_first_ordinal
            and current.source_record_count == envelope.record_count
            and hmac.compare_digest(
                current.source_batch_fingerprint,
                envelope.source_refs_fingerprint)
            and hmac.compare_digest(
                current.payload_fingerprint, envelope.payload_fingerprint)
            and current.payload_bytes == envelope.payload_bytes
            and current.input_tokens == envelope.input_tokens
            and current.egress_authorization_ref
            == proof.egress_authorization_ref
            and ((error_code == "RAG_PROVIDER_REQUEST_REJECTED"
                  and response_ref is None)
                 or (error_code == "RAG_EMBEDDING_RESPONSE_INVALID"
                     and response_ref is not None))
        )
