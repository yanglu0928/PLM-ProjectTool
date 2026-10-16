"""Parameterized PostgreSQL PROJECT FTS over one exact ACTIVE Index snapshot."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, bindparam, cast, func, literal_column, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow,
    DocumentVersionRow,
)
from plm_assistant.modules.rag.application.prepare_retrieval_query import (
    PreparedRAGRetrieval,
    RAGRetrievalPreparationError,
)
from plm_assistant.modules.rag.application.project_fts_candidates import (
    ProjectFTSCandidate,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    DocumentChunkRow,
    EmbeddingRecordRow,
    IndexSourceChunkRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active PROJECT FTS transaction required")
    return session


class SqlAlchemyProjectFTSCandidateRepository:
    def project_fts(self, transaction: object, *, prepared: PreparedRAGRetrieval
                    ) -> tuple[ProjectFTSCandidate, ...]:
        if type(prepared) is not PreparedRAGRetrieval:
            raise RAGRetrievalPreparationError("RAG_FTS_CANDIDATE_UNAVAILABLE")
        query_text = prepared.query_utf8.decode("utf-8", errors="strict")
        tsquery = func.websearch_to_tsquery(
            literal_column("'simple'::regconfig"), bindparam("query_text"),
        )
        rank = func.ts_rank_cd(DocumentChunkRow.search_vector, tsquery, 32)
        score = cast(func.round(rank * 1_000_000), BigInteger).label("score_micros")
        statement = select(
            IndexSourceChunkRow.source_ordinal,
            DocumentChunkRow.chunk_id,
            DocumentChunkRow.document_version_ref,
            DocumentChunkRow.parse_result_ref,
            DocumentChunkRow.source_type,
            DocumentChunkRow.source_locator,
            score,
        ).join(
            DocumentChunkRow,
            DocumentChunkRow.chunk_id == IndexSourceChunkRow.chunk_id,
        ).join(
            EmbeddingRecordRow,
            (EmbeddingRecordRow.embedding_index_id
             == IndexSourceChunkRow.embedding_index_id)
            & (EmbeddingRecordRow.chunk_id == IndexSourceChunkRow.chunk_id)
            & (EmbeddingRecordRow.embedding_state == "AVAILABLE"),
        ).join(
            DocumentVersionRow,
            DocumentVersionRow.document_version_id
            == DocumentChunkRow.document_version_ref,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).where(
            IndexSourceChunkRow.embedding_index_id == prepared.project_index_ref,
            IndexSourceChunkRow.scope == "PROJECT",
            IndexSourceChunkRow.project_id == prepared.project_id,
            DocumentChunkRow.scope == "PROJECT",
            DocumentChunkRow.project_id == prepared.project_id,
            DocumentChunkRow.chunk_state == "ACTIVE",
            DocumentChunkRow.text_fingerprint
            == IndexSourceChunkRow.chunk_text_fingerprint,
            EmbeddingRecordRow.scope == "PROJECT",
            EmbeddingRecordRow.project_id == prepared.project_id,
            EmbeddingRecordRow.embedding_model_ref == prepared.project_model_ref,
            EmbeddingRecordRow.chunk_text_fingerprint
            == IndexSourceChunkRow.chunk_text_fingerprint,
            DocumentVersionRow.scope == "PROJECT",
            DocumentVersionRow.project_id == prepared.project_id,
            DocumentVersionRow.availability_state == "AVAILABLE",
            DocumentRow.scope == "PROJECT",
            DocumentRow.project_id == prepared.project_id,
            DocumentRow.document_state == "ACTIVE",
            DocumentChunkRow.search_vector.op("@@")(tsquery),
        )
        metadata = prepared.metadata_filter
        source_types = metadata.get("source_type")
        if source_types is not None:
            statement = statement.where(DocumentChunkRow.source_type.in_(source_types))
        categories = metadata.get("document_category")
        if categories is not None:
            statement = statement.where(DocumentRow.document_category.in_(categories))
        document_version = metadata.get("document_version_ref")
        if document_version is not None:
            statement = statement.where(
                DocumentChunkRow.document_version_ref == uuid.UUID(document_version),
            )
        if set(metadata) - {
                "document_category", "source_type", "document_version_ref"}:
            raise RAGRetrievalPreparationError("RAG_METADATA_FILTER_NOT_ALLOWED")
        pool_size = min(prepared.top_k * 4, 400)
        rows = _session(transaction).execute(
            statement.order_by(
                rank.desc(), IndexSourceChunkRow.source_ordinal,
                DocumentChunkRow.chunk_id,
            ).limit(pool_size), {"query_text": query_text},
        ).all()
        return tuple(ProjectFTSCandidate(
            ordinal, prepared.project_index_ref, prepared.project_model_ref,
            row.chunk_id, row.document_version_ref, row.parse_result_ref,
            row.source_type, dict(row.source_locator), "FTS",
            max(0, min(int(row.score_micros), 1_000_000_000)),
            prepared.authorization_snapshot_fingerprint,
        ) for ordinal, row in enumerate(rows))
