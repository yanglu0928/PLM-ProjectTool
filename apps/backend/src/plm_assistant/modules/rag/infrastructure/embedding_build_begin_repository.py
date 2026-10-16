"""PostgreSQL transition from a sealed plan to one running build."""

from __future__ import annotations

from sqlalchemy import select

from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildRow,
    EmbeddingIndexRow,
)


class SqlAlchemyRAGEmbeddingBuildBeginRepository:
    def begin(self, transaction: object, *, claim: RAGIndexBuildClaim) -> None:
        if type(claim) is not RAGIndexBuildClaim:
            raise RuntimeError("invalid RAG build claim")
        claim.__post_init__()
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        build = session.scalar(select(EmbeddingBuildRow).where(
            EmbeddingBuildRow.embedding_build_id == claim.embedding_build_id,
        ).with_for_update(of=EmbeddingBuildRow).execution_options(autoflush=False))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == claim.embedding_index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(autoflush=False))
        if (build is None or index is None
                or build.embedding_index_id != claim.embedding_index_id
                or build.build_job_ref != claim.job_id
                or build.build_generation != claim.build_generation
                or build.scope != claim.scope or build.project_id != claim.project_id
                or build.created_by != claim.actor_id
                or build.build_state != "PLANNED" or build.lock_version != 0
                or index.scope != claim.scope or index.project_id != claim.project_id
                or index.index_state != "PLANNED" or index.lock_version != 0
                or build.embedding_model_ref != index.embedding_model_ref
                or build.embedding_dimension != index.embedding_dimension
                or build.source_chunk_count != index.source_chunk_count
                or build.source_snapshot_fingerprint != index.source_snapshot_fingerprint):
            raise RuntimeError("RAG build plan is not startable")
        build.build_state = "RUNNING"
        build.lock_version = 1
        session.flush()
        index.index_state = "BUILDING"
        index.lock_version = 1
        session.flush()
