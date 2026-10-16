"""PostgreSQL atomic successful Batch and EmbeddingRecord publication."""

from __future__ import annotations

import hmac

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_pre_send import (
    AuthorizedAIEmbeddingSend,
)
from plm_assistant.modules.ai.application.embedding_response_contract import (
    ParsedAIEmbeddingResponse,
)
from plm_assistant.modules.jobs.application.rag_index_build_claim import (
    RAGIndexBuildClaim,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.rag.application.embedding_batch_success import (
    PublishedRAGEmbeddingBatch,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
    EmbeddingIndexRow,
    EmbeddingRecordRow,
    IndexSourceChunkRow,
)


class SqlAlchemyRAGEmbeddingBatchSuccessRepository:
    def publish(self, transaction: object, *, claim: RAGIndexBuildClaim,
                envelope: AIEmbeddingEnvelope,
                send: AuthorizedAIEmbeddingSend,
                parsed: ParsedAIEmbeddingResponse
                ) -> PublishedRAGEmbeddingBatch | None:
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        build = session.scalar(select(EmbeddingBuildRow).where(
            EmbeddingBuildRow.embedding_build_id == claim.embedding_build_id,
            EmbeddingBuildRow.embedding_index_id == claim.embedding_index_id,
            EmbeddingBuildRow.build_job_ref == claim.job_id,
        ).with_for_update(of=EmbeddingBuildRow).execution_options(autoflush=False))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == claim.embedding_index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(autoflush=False))
        batch = session.scalar(select(EmbeddingBuildBatchRow).where(
            EmbeddingBuildBatchRow.embedding_build_batch_id
            == envelope.embedding_build_batch_id,
            EmbeddingBuildBatchRow.embedding_build_id
            == claim.embedding_build_id,
            EmbeddingBuildBatchRow.batch_ordinal == envelope.batch_ordinal,
        ).with_for_update(of=EmbeddingBuildBatchRow)
         .execution_options(autoflush=False))
        if not self._current(build, index, batch, claim, envelope, send):
            return None
        sources = session.scalars(select(IndexSourceChunkRow).where(
            IndexSourceChunkRow.embedding_index_id == claim.embedding_index_id,
            IndexSourceChunkRow.source_ordinal >= envelope.source_first_ordinal,
            IndexSourceChunkRow.source_ordinal < (
                envelope.source_first_ordinal + envelope.record_count),
        ).order_by(IndexSourceChunkRow.source_ordinal)
         .with_for_update(read=True, of=IndexSourceChunkRow)
         .execution_options(autoflush=False)).all()
        if (len(sources) != envelope.record_count
                or any(source.source_ordinal != expected
                       for source, expected in zip(
                           sources,
                           range(envelope.source_first_ordinal,
                                 envelope.source_first_ordinal
                                 + envelope.record_count), strict=True))
                or any(not hmac.compare_digest(
                    source.chunk_text_fingerprint,
                    envelope.source_text_fingerprints[offset])
                    for offset, source in enumerate(sources))):
            return None
        completed_at = session.scalar(select(func.clock_timestamp()))
        if (completed_at is None or completed_at < batch.started_at
                or completed_at >= claim.lease_expires_at):
            return None
        batch.batch_state = "SUCCEEDED"
        batch.provider_request_ref = parsed.provider_request_ref
        batch.completed_at = completed_at
        batch.lock_version += 1
        session.flush()
        rows = []
        for source, vector in zip(sources, parsed.vectors, strict=True):
            row = EmbeddingRecordRow(
                scope=claim.scope, project_id=claim.project_id,
                embedding_index_id=claim.embedding_index_id,
                chunk_id=source.chunk_id,
                embedding_model_ref=build.embedding_model_ref,
                embedding_dimension=build.embedding_dimension,
                chunk_text_fingerprint=source.chunk_text_fingerprint,
                embedding_vector=list(vector.values),
                vector_fingerprint=vector.vector_fingerprint,
                embedding_state="AVAILABLE",
                provider_request_ref=parsed.provider_request_ref,
                egress_authorization_ref=send.proof.egress_authorization_ref,
                created_at=completed_at,
            )
            session.add(row)
            rows.append(row)
        session.flush()
        ids = tuple(row.embedding_record_id for row in rows)
        return PublishedRAGEmbeddingBatch(
            batch.embedding_build_batch_id, ids,
            parsed.provider_request_ref, completed_at,
        )

    @staticmethod
    def _current(build, index, batch, claim: RAGIndexBuildClaim,
                 envelope: AIEmbeddingEnvelope,
                 send: AuthorizedAIEmbeddingSend) -> bool:
        proof = send.proof
        return bool(
            build is not None and index is not None and batch is not None
            and build.build_state == "RUNNING" and build.lock_version == 1
            and build.build_generation == claim.build_generation == 1
            and build.created_by == claim.actor_id
            and (build.scope, build.project_id) == (claim.scope, claim.project_id)
            and index.index_state == "BUILDING" and index.lock_version == 1
            and (index.scope, index.project_id) == (claim.scope, claim.project_id)
            and index.embedding_model_ref == build.embedding_model_ref
            and index.embedding_dimension == build.embedding_dimension
            and batch.batch_state == "RUNNING" and batch.lock_version == 1
            and batch.send_fencing_token == claim.fencing_token == 1
            and batch.provider_request_ref is None and batch.error_code is None
            and batch.started_at is not None and batch.completed_at is None
            and batch.source_first_ordinal == envelope.source_first_ordinal
            and batch.source_record_count == envelope.record_count
            and hmac.compare_digest(
                batch.source_batch_fingerprint,
                envelope.source_refs_fingerprint)
            and hmac.compare_digest(
                batch.payload_fingerprint, envelope.payload_fingerprint)
            and batch.payload_bytes == envelope.payload_bytes
            and batch.input_tokens == envelope.input_tokens
            and batch.egress_authorization_ref
            == proof.egress_authorization_ref
        )
