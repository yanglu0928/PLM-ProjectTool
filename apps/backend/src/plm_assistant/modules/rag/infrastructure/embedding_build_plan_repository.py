"""PostgreSQL creation of a sealed RAG embedding build plan and Job owner."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select

from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.rag.application.embedding_build_plan import (
    PlannedRAGEmbeddingBuild,
    RAGEmbeddingBuildPlanRequest,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
    EmbeddingIndexRow,
)


class SqlAlchemyRAGEmbeddingBuildPlanRepository:
    def create(self, transaction: object, *, request: RAGEmbeddingBuildPlanRequest,
               embedding_build_id: uuid.UUID, job_id: uuid.UUID
               ) -> PlannedRAGEmbeddingBuild:
        request.__post_init__()
        if any(type(value) is not uuid.UUID or not value.int
               for value in (embedding_build_id, job_id)):
            raise RuntimeError("invalid RAG build identity")
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == request.embedding_index_id,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(autoflush=False))
        source_count = sum(batch.source_record_count for batch in request.batches)
        if (index is None or index.index_state != "PLANNED" or index.lock_version != 0
                or index.embedding_dimension not in {768, 1024}
                or index.source_chunk_count != source_count):
            raise RuntimeError("RAG index is not plannable")
        authorization_canonical = "\n".join(
            f"{batch.batch_ordinal}:{batch.egress_authorization_ref}:"
            f"{batch.source_batch_fingerprint.hex()}:{batch.payload_fingerprint.hex()}"
            for batch in request.batches
        )
        authorization_fingerprint = hashlib.sha256(
            authorization_canonical.encode("utf-8")
        ).digest()
        build_canonical = (
            f"{index.embedding_index_id}:1:{index.source_snapshot_fingerprint.hex()}:"
            f"{authorization_fingerprint.hex()}:{len(request.batches)}"
        )
        build_fingerprint = hashlib.sha256(build_canonical.encode("utf-8")).digest()
        session.add(JobRow(
            job_id=job_id,
            owner_module="rag",
            job_type="RAG_INDEX_BUILD",
            scope=index.scope,
            project_id=index.project_id,
            actor_ref=request.actor_id,
            trace_id=str(request.trace_id),
            payload_refs={
                "embedding_build_id": str(embedding_build_id),
                "embedding_index_id": str(index.embedding_index_id),
                "build_generation": 1,
            },
            idempotency_key=f"rag-index-build:{index.embedding_index_id}:1",
            max_attempts=1,
        ))
        session.flush()
        session.add(EmbeddingBuildRow(
            embedding_build_id=embedding_build_id,
            embedding_index_id=index.embedding_index_id,
            scope=index.scope,
            project_id=index.project_id,
            embedding_model_ref=index.embedding_model_ref,
            embedding_dimension=index.embedding_dimension,
            build_generation=1,
            build_job_ref=job_id,
            source_chunk_count=index.source_chunk_count,
            source_snapshot_fingerprint=index.source_snapshot_fingerprint,
            batch_count=len(request.batches),
            authorization_set_fingerprint=authorization_fingerprint,
            build_fingerprint=build_fingerprint,
            created_by=request.actor_id,
        ))
        session.flush()
        for batch in request.batches:
            session.add(EmbeddingBuildBatchRow(
                embedding_build_id=embedding_build_id,
                batch_ordinal=batch.batch_ordinal,
                source_first_ordinal=batch.source_first_ordinal,
                source_record_count=batch.source_record_count,
                source_batch_fingerprint=batch.source_batch_fingerprint,
                payload_fingerprint=batch.payload_fingerprint,
                payload_bytes=batch.payload_bytes,
                input_tokens=batch.input_tokens,
                egress_authorization_ref=batch.egress_authorization_ref,
            ))
        session.flush()
        return PlannedRAGEmbeddingBuild(
            embedding_build_id, index.embedding_index_id, job_id,
        )
