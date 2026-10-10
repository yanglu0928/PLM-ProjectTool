"""PostgreSQL current-fact snapshot for authorized Retrieval query use."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaim
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    RAGRetrievalExecutionTarget,
    RAGRetrievalPreparationError,
)
from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    RetrievalQueryEnvelope,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    DocumentChunkRow,
    EmbeddingIndexRow,
    EmbeddingRecordRow,
    IndexSourceChunkRow,
    RetrievalQueryContentRow,
    RetrievalRunRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active RAG Retrieval preparation transaction required")
    return session


class SqlAlchemyRAGRetrievalQueryPreparationRepository:
    def actor_enabled(self, transaction: object, *, actor_id: uuid.UUID) -> bool:
        if type(actor_id) is not uuid.UUID or not actor_id.int:
            return False
        state = _session(transaction).scalar(select(UserRow.state).where(
            UserRow.user_id == actor_id,
        ).with_for_update(of=UserRow))
        return state == "ENABLED"

    def locked_target(self, transaction: object, *, claim: RAGRetrievalClaim,
                      now: datetime) -> RAGRetrievalExecutionTarget | None:
        if (type(claim) is not RAGRetrievalClaim
                or not isinstance(now, datetime)
                or now.tzinfo is None or now.utcoffset() is None):
            raise RAGRetrievalPreparationError("VALIDATION_FAILED")
        session = _session(transaction)
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.retrieval_run_id == claim.retrieval_run_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(populate_existing=True))
        if (run is None or run.job_id != claim.job_id
                or run.scope != "PROJECT" or run.project_id != claim.project_id
                or run.actor_ref != claim.actor_id or run.trace_id != claim.trace_id
                or run.retrieval_state != "RUNNING" or run.lock_version != 0
                or run.completed_at is not None or run.error_code is not None
                or run.project_index_ref is None or run.global_index_ref is not None
                or run.retrieval_policy_ref != "fts.project.v1"
                or run.rerank_policy_ref != "none.v1"
                or run.rerank_state != "NOT_APPLICABLE"
                or run.egress_state != "NOT_APPLICABLE"
                or run.degraded or run.quality_flags != []):
            return None
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == run.project_index_ref,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(populate_existing=True))
        if (index is None or index.index_state != "ACTIVE"
                or index.scope != "PROJECT" or index.project_id != claim.project_id):
            return None
        model = session.get(AIModelRow, index.embedding_model_ref)
        if (model is None or model.model_kind != "EMBEDDING"
                or model.model_state != "AVAILABLE"
                or model.embedding_dimension != index.embedding_dimension):
            return None
        sources = session.execute(select(
            IndexSourceChunkRow.scope, IndexSourceChunkRow.project_id,
            IndexSourceChunkRow.chunk_text_fingerprint,
            DocumentChunkRow.scope, DocumentChunkRow.project_id,
            DocumentChunkRow.chunk_state, DocumentChunkRow.text_fingerprint,
            EmbeddingRecordRow.scope, EmbeddingRecordRow.project_id,
            EmbeddingRecordRow.embedding_model_ref,
            EmbeddingRecordRow.embedding_dimension,
            EmbeddingRecordRow.chunk_text_fingerprint,
            EmbeddingRecordRow.embedding_state,
        ).join(
            DocumentChunkRow,
            DocumentChunkRow.chunk_id == IndexSourceChunkRow.chunk_id,
        ).join(
            EmbeddingRecordRow,
            (EmbeddingRecordRow.embedding_index_id
             == IndexSourceChunkRow.embedding_index_id)
            & (EmbeddingRecordRow.chunk_id == IndexSourceChunkRow.chunk_id)
            & (EmbeddingRecordRow.embedding_state == "AVAILABLE"),
        ).where(
            IndexSourceChunkRow.embedding_index_id == index.embedding_index_id,
        ).order_by(
            IndexSourceChunkRow.source_ordinal,
        ).with_for_update(of=(
            IndexSourceChunkRow, DocumentChunkRow, EmbeddingRecordRow,
        )).execution_options(populate_existing=True)).all()
        if (len(sources) != index.source_chunk_count
                or any(
                    source[0] != "PROJECT" or source[1] != claim.project_id
                    or source[3] != "PROJECT" or source[4] != claim.project_id
                    or source[5] != "ACTIVE"
                    or bytes(source[2]) != bytes(source[6])
                    or source[7] != "PROJECT" or source[8] != claim.project_id
                    or source[9] != index.embedding_model_ref
                    or source[10] != index.embedding_dimension
                    or bytes(source[2]) != bytes(source[11])
                    or source[12] != "AVAILABLE"
                    for source in sources
                )):
            return None
        content = session.scalar(select(RetrievalQueryContentRow).where(
            RetrievalQueryContentRow.retrieval_run_id == run.retrieval_run_id,
        ).with_for_update(of=RetrievalQueryContentRow).execution_options(
            populate_existing=True,
        ))
        if (content is None or content.project_id != run.project_id
                or bytes(content.query_fingerprint) != bytes(run.query_fingerprint)
                or content.retention_until <= now):
            return None
        envelope = RetrievalQueryEnvelope(
            run.retrieval_run_id, run.project_id, bytes(run.query_fingerprint),
            bytes(content.encrypted_payload), dict(content.encryption_metadata),
            content.key_provider_ref, content.plaintext_bytes,
            content.retention_until,
        )
        return RAGRetrievalExecutionTarget(
            run.retrieval_run_id, run.job_id, run.project_id, run.actor_ref,
            run.trace_id, index.embedding_index_id, index.embedding_model_ref,
            index.index_version, index.lock_version, index.source_chunk_count,
            bytes(index.source_snapshot_fingerprint), dict(run.metadata_filter),
            bytes(run.metadata_filter_fingerprint), run.retrieval_policy_ref,
            run.rerank_policy_ref, run.top_k, envelope,
        )
