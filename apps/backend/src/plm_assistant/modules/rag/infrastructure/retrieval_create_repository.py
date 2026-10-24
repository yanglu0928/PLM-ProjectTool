"""PostgreSQL atomic Job, RetrievalRun and ciphertext QueryContent creation."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.jobs.infrastructure.orm import JobRow
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.rag.application.create_retrieval import (
    CreatedProjectRetrieval,
    RAGRetrievalCreateError,
    RAGRetrievalCreateTarget,
    RAGRetrievalPersistenceRequest,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    DocumentChunkRow,
    EmbeddingIndexRow,
    IndexSourceChunkRow,
    RetrievalQueryContentRow,
    RetrievalRunRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active RAG Retrieval transaction required")
    return session


class SqlAlchemyRAGRetrievalCreateRepository:
    def locked_target(
        self,
        transaction: object,
        *,
        project_id: uuid.UUID,
        project_index_ref: uuid.UUID,
        global_index_ref: uuid.UUID | None,
    ) -> RAGRetrievalCreateTarget | None:
        if (any(type(value) is not uuid.UUID or not value.int
                for value in (project_id, project_index_ref))
                or (global_index_ref is not None and
                    (type(global_index_ref) is not uuid.UUID
                     or not global_index_ref.int))):
            raise RAGRetrievalCreateError("VALIDATION_FAILED")
        session = _session(transaction)
        ids = sorted(
            {project_index_ref, *(() if global_index_ref is None
                                  else (global_index_ref,))},
            key=lambda value: value.int,
        )
        rows = session.scalars(
            select(EmbeddingIndexRow)
            .where(EmbeddingIndexRow.embedding_index_id.in_(ids))
            .order_by(EmbeddingIndexRow.embedding_index_id)
            .with_for_update(of=EmbeddingIndexRow)
            .execution_options(autoflush=False, populate_existing=True)
        ).all()
        indexed = {row.embedding_index_id: row for row in rows}
        project_index = indexed.get(project_index_ref)
        global_index = (indexed.get(global_index_ref)
                        if global_index_ref is not None else None)
        if (project_index is None or project_index.index_state != "ACTIVE"
                or project_index.scope != "PROJECT"
                or project_index.project_id != project_id
                or (global_index_ref is not None and (
                    global_index is None or global_index.index_state != "ACTIVE"
                    or global_index.scope != "GLOBAL"
                    or global_index.project_id is not None))):
            return None
        for index in (project_index, global_index):
            if index is None:
                continue
            model = session.get(AIModelRow, index.embedding_model_ref)
            invalid_source = session.scalar(select(exists().where(
                IndexSourceChunkRow.embedding_index_id == index.embedding_index_id,
                IndexSourceChunkRow.chunk_id == DocumentChunkRow.chunk_id,
                (DocumentChunkRow.chunk_state != "ACTIVE")
                | (DocumentChunkRow.text_fingerprint
                   != IndexSourceChunkRow.chunk_text_fingerprint),
            )))
            if (model is None or model.model_kind != "EMBEDDING"
                    or model.model_state != "AVAILABLE"
                    or model.embedding_dimension != index.embedding_dimension
                    or invalid_source):
                return None
        return RAGRetrievalCreateTarget(
            project_id, project_index.embedding_index_id,
            project_index.embedding_model_ref,
            global_index.embedding_index_id if global_index else None,
            global_index.embedding_model_ref if global_index else None,
        )

    def create(self, transaction: object, *, request: RAGRetrievalPersistenceRequest
               ) -> CreatedProjectRetrieval:
        if type(request) is not RAGRetrievalPersistenceRequest:
            raise RAGRetrievalCreateError("VALIDATION_FAILED")
        session = _session(transaction)
        encrypted = request.encrypted_query
        if (encrypted.retrieval_run_id != request.retrieval_run_id
                or encrypted.project_id != request.project_id
                or encrypted.query_fingerprint != request.query_fingerprint):
            raise RAGRetrievalCreateError("RAG_QUERY_ENCRYPTION_UNAVAILABLE")
        job_id = uuid.UUID(new_uuid7())
        session.execute(insert(JobRow).values(
            job_id=job_id, owner_module="rag", job_type="RAG_RETRIEVAL",
            scope="PROJECT", project_id=request.project_id,
            actor_ref=request.actor_id, trace_id=str(request.trace_id),
            payload_refs={"retrieval_run_id": str(request.retrieval_run_id)},
            idempotency_key=str(request.retrieval_run_id), max_attempts=1,
        ))
        session.execute(insert(RetrievalRunRow).values(
            retrieval_run_id=request.retrieval_run_id, scope="PROJECT",
            project_id=request.project_id, actor_ref=request.actor_id,
            query_fingerprint=request.query_fingerprint,
            metadata_filter=request.metadata_filter,
            metadata_filter_fingerprint=request.metadata_filter_fingerprint,
            global_index_ref=request.target.global_index_ref,
            project_index_ref=request.target.project_index_ref,
            retrieval_policy_ref=request.retrieval_policy_ref,
            rerank_policy_ref=request.rerank_policy_ref, top_k=request.top_k,
            rerank_state="NOT_APPLICABLE", egress_state="NOT_APPLICABLE",
            retrieval_state="RUNNING", quality_flags=[], degraded=False,
            job_id=job_id, trace_id=request.trace_id,
        ))
        session.execute(insert(RetrievalQueryContentRow).values(
            retrieval_run_id=request.retrieval_run_id,
            project_id=request.project_id,
            query_fingerprint=request.query_fingerprint,
            encrypted_payload=encrypted.encrypted_payload,
            encryption_metadata=encrypted.encryption_metadata,
            key_provider_ref=encrypted.key_provider_ref,
            plaintext_bytes=encrypted.plaintext_bytes,
            retention_until=encrypted.retention_until,
        ))
        session.flush()
        return CreatedProjectRetrieval(
            request.retrieval_run_id, job_id, request.project_id,
            request.query_fingerprint,
        )

    def replay(self, transaction: object, *, retrieval_run_id: uuid.UUID,
               project_id: uuid.UUID,
               actor_id: uuid.UUID) -> CreatedProjectRetrieval | None:
        if any(type(value) is not uuid.UUID or not value.int for value in (
                retrieval_run_id, project_id, actor_id)):
            return None
        session = _session(transaction)
        row = session.execute(select(
            RetrievalRunRow.retrieval_run_id, RetrievalRunRow.job_id,
            RetrievalRunRow.project_id, RetrievalRunRow.actor_ref,
            RetrievalRunRow.query_fingerprint, RetrievalRunRow.retrieval_state,
        ).where(
            RetrievalRunRow.retrieval_run_id == retrieval_run_id,
            RetrievalRunRow.project_id == project_id,
            RetrievalRunRow.actor_ref == actor_id,
        ).execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == row.job_id, JobRow.owner_module == "rag",
            JobRow.job_type == "RAG_RETRIEVAL", JobRow.scope == "PROJECT",
            JobRow.project_id == project_id, JobRow.actor_ref == actor_id,
        ).execution_options(autoflush=False))
        if (job is None
                or job.payload_refs != {"retrieval_run_id": str(retrieval_run_id)}
                or row.retrieval_state != "RUNNING"):
            return None
        return CreatedProjectRetrieval(
            row.retrieval_run_id, row.job_id, row.project_id,
            bytes(row.query_fingerprint), row.retrieval_state,
        )
