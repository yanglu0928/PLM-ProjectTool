"""PostgreSQL owner for atomic Retrieval result and terminal publication."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import func, select, text

from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaim
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow, JobLeaseRow, JobRow
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.rag.application.fts_retrieval_merge import FTSRetrievalMergePlan
from plm_assistant.modules.rag.application.prepare_retrieval_query import PreparedRAGRetrieval
from plm_assistant.modules.rag.application.retrieval_terminal import (
    PublishedRAGRetrievalTerminal,
    RAGRetrievalTerminalError,
    context_bundle_fingerprint,
    require_terminal_error_code,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    ContextBundleRow,
    ContextItemRow,
    DocumentChunkRow,
    EmbeddingIndexRow,
    RetrievalCandidateRow,
    RetrievalRunRow,
    RetrievalScorePartRow,
)


_CONSTRAINTS = (
    "plm.trg_rag_retrieval_run_terminal_complete,"
    "plm.trg_rag_retrieval_job_terminal_complete,"
    "plm.trg_rag_retrieval_candidate_terminal_complete,"
    "plm.trg_rag_retrieval_score_terminal_complete,"
    "plm.trg_rag_context_bundle_terminal_complete,"
    "plm.trg_rag_context_item_terminal_complete"
)


class SqlAlchemyRAGRetrievalTerminalRepository:
    CONTEXT_POLICY_REF = "project-documents.v1"
    CONTEXT_TOKEN_BUDGET = 1_048_576

    def __init__(self) -> None:
        self._leases = SqlAlchemyJobLeaseRepository()

    def publish_success(
        self, transaction: object, *, claim: RAGRetrievalClaim,
        prepared: PreparedRAGRetrieval, plan: FTSRetrievalMergePlan,
        worker_ref: str,
    ) -> PublishedRAGRetrievalTerminal:
        claim.__post_init__()
        prepared.__post_init__()
        plan.__post_init__()
        if ((prepared.retrieval_run_id, prepared.job_id, prepared.project_id,
             prepared.actor_id, prepared.trace_id) !=
                (claim.retrieval_run_id, claim.job_id, claim.project_id,
                 claim.actor_id, claim.trace_id)
                or prepared.project_index_ref is None
                or plan.retrieval_policy_ref != prepared.retrieval_policy_ref
                or len(plan.candidates) > prepared.top_k
                or any(
                    item.candidate.embedding_index_id
                    != prepared.project_index_ref
                    or item.candidate.embedding_model_ref
                    != prepared.project_model_ref
                    or item.candidate.authorization_snapshot_fingerprint
                    != prepared.authorization_snapshot_fingerprint
                    or item.final_score_micros <= 0
                    for item in plan.candidates
                )):
            raise RAGRetrievalTerminalError()
        session = self._leases._session(transaction)
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.retrieval_run_id == claim.retrieval_run_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(populate_existing=True))
        index = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == prepared.project_index_ref,
        ).with_for_update(of=EmbeddingIndexRow).execution_options(populate_existing=True))
        if not self._current_run(run, index, claim, prepared):
            raise RAGRetrievalTerminalError()
        chunk_ids = tuple(item.candidate.chunk_id for item in plan.candidates)
        chunks = list(session.scalars(select(DocumentChunkRow).where(
            DocumentChunkRow.chunk_id.in_(chunk_ids),
        ).with_for_update(of=DocumentChunkRow).execution_options(populate_existing=True)))
        by_id = {row.chunk_id: row for row in chunks}
        if len(by_id) != len(chunk_ids):
            raise RAGRetrievalTerminalError()

        candidate_rows: list[RetrievalCandidateRow] = []
        score_rows: list[RetrievalScorePartRow] = []
        item_material: list[tuple[uuid.UUID, object, str, bytes, int]] = []
        for ranked in plan.candidates:
            source = ranked.candidate
            chunk = by_id.get(source.chunk_id)
            if (chunk is None or chunk.scope != "PROJECT"
                    or chunk.project_id != claim.project_id
                    or chunk.chunk_state != "ACTIVE"
                    or chunk.document_version_ref != source.document_version_ref
                    or chunk.parse_result_ref != source.parse_result_ref
                    or chunk.source_type != source.source_type
                    or dict(chunk.source_locator) != source.source_locator
                    or not chunk.search_body):
                raise RAGRetrievalTerminalError()
            candidate_id = uuid.UUID(new_uuid7())
            candidate_rows.append(RetrievalCandidateRow(
                candidate_id=candidate_id,
                retrieval_run_id=claim.retrieval_run_id,
                run_project_id=claim.project_id,
                candidate_scope="PROJECT",
                candidate_project_id=claim.project_id,
                embedding_index_id=source.embedding_index_id,
                embedding_model_ref=source.embedding_model_ref,
                chunk_id=source.chunk_id,
                document_version_ref=source.document_version_ref,
                parse_result_ref=source.parse_result_ref,
                source_type=source.source_type,
                source_locator=dict(source.source_locator),
                retrieval_channel="FTS",
                candidate_ordinal=ranked.final_ordinal,
                final_score_micros=ranked.final_score_micros,
                authorization_snapshot_fingerprint=(
                    source.authorization_snapshot_fingerprint
                ),
            ))
            for part in ranked.score_parts:
                part.__post_init__()
                score_rows.append(RetrievalScorePartRow(
                    score_part_id=uuid.UUID(new_uuid7()),
                    retrieval_run_id=claim.retrieval_run_id,
                    project_id=claim.project_id,
                    candidate_id=candidate_id,
                    score_kind=part.score_kind,
                    score_ordinal=part.score_ordinal,
                    raw_score_micros=part.raw_score_micros,
                    normalized_score_micros=part.normalized_score_micros,
                    weight_micros=part.weight_micros,
                    weighted_score_micros=part.weighted_score_micros,
                    score_policy_ref=part.score_policy_ref,
                ))
            snippet = chunk.search_body[:8192]
            snippet_fingerprint = hashlib.sha256(snippet.encode("utf-8")).digest()
            item_material.append((
                candidate_id, source, snippet, snippet_fingerprint, len(snippet),
            ))

        self._leases.finish(
            transaction, job_id=claim.job_id,
            fencing_token=claim.fencing_token, worker_ref=worker_ref,
        )
        job = session.get(JobRow, claim.job_id, populate_existing=True)
        if job is None or job.completed_at is None:
            raise RAGRetrievalTerminalError()
        run.retrieval_state = "SUCCEEDED"
        run.rerank_state = plan.rerank_state
        run.egress_state = plan.egress_state
        run.quality_flags = list(plan.quality_flags)
        run.degraded = plan.degraded
        run.error_code = None
        run.completed_at = job.completed_at
        run.lock_version = 1
        session.add_all(candidate_rows)
        session.add_all(score_rows)
        session.flush()

        bundle_id = uuid.UUID(new_uuid7())
        facts = tuple((
            ordinal, candidate.candidate_id, material[1].chunk_id,
            material[3], material[1].authorization_snapshot_fingerprint,
        ) for ordinal, (candidate, material) in enumerate(
            zip(candidate_rows, item_material, strict=True)
        ))
        bundle_fingerprint = context_bundle_fingerprint(
            retrieval_run_id=claim.retrieval_run_id,
            project_id=claim.project_id, item_facts=facts,
        )
        token_count = sum(material[4] for material in item_material)
        bundle = ContextBundleRow(
            context_bundle_id=bundle_id,
            retrieval_run_id=claim.retrieval_run_id,
            project_id=claim.project_id,
            context_policy_ref=self.CONTEXT_POLICY_REF,
            bundle_fingerprint=bundle_fingerprint,
            item_count=len(candidate_rows),
            token_budget=self.CONTEXT_TOKEN_BUDGET,
            token_count=token_count,
        )
        session.add(bundle)
        for ordinal, (candidate, material) in enumerate(
                zip(candidate_rows, item_material, strict=True)):
            source, snippet, snippet_fingerprint, snippet_tokens = material[1:]
            session.add(ContextItemRow(
                context_item_id=uuid.UUID(new_uuid7()),
                context_bundle_id=bundle_id,
                retrieval_run_id=claim.retrieval_run_id,
                project_id=claim.project_id,
                candidate_id=candidate.candidate_id,
                item_ordinal=ordinal,
                chunk_id=source.chunk_id,
                document_version_ref=source.document_version_ref,
                source_locator=dict(source.source_locator),
                snippet_start=0,
                snippet_end=len(snippet),
                token_count=snippet_tokens,
                snippet_fingerprint=snippet_fingerprint,
                access_snapshot_fingerprint=(
                    source.authorization_snapshot_fingerprint
                ),
            ))
        session.flush()
        self._validate_constraints(session)
        return PublishedRAGRetrievalTerminal(
            claim.retrieval_run_id, claim.job_id, claim.project_id,
            claim.actor_id, claim.trace_id, "SUCCEEDED", len(candidate_rows),
            bundle_id, bundle_fingerprint, None, job.completed_at,
        )

    def publish_failure(
        self, transaction: object, *, claim: RAGRetrievalClaim,
        worker_ref: str, error_code: str,
    ) -> PublishedRAGRetrievalTerminal:
        error_code = require_terminal_error_code(error_code)
        if error_code == "RAG_RETRIEVAL_LEASE_EXPIRED":
            raise RAGRetrievalTerminalError("VALIDATION_FAILED")
        session = self._leases._session(transaction)
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.retrieval_run_id == claim.retrieval_run_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(populate_existing=True))
        if (run is None or run.retrieval_state != "RUNNING"
                or run.lock_version != 0 or run.job_id != claim.job_id
                or run.project_id != claim.project_id
                or run.actor_ref != claim.actor_id or run.trace_id != claim.trace_id):
            raise RAGRetrievalTerminalError()
        state = self._leases.retry_or_fail(
            transaction, job_id=claim.job_id,
            fencing_token=claim.fencing_token, worker_ref=worker_ref,
            error_code=error_code, retryable=False, delay_seconds=0,
        )
        if state != "FAILED":
            raise RAGRetrievalTerminalError()
        job = session.get(JobRow, claim.job_id, populate_existing=True)
        if job is None or job.completed_at is None:
            raise RAGRetrievalTerminalError()
        run.retrieval_state = "FAILED"
        run.rerank_state = "NOT_APPLICABLE"
        run.egress_state = "NOT_APPLICABLE"
        run.quality_flags = []
        run.degraded = False
        run.error_code = error_code
        run.completed_at = job.completed_at
        run.lock_version = 1
        session.flush()
        self._validate_constraints(session)
        return PublishedRAGRetrievalTerminal(
            claim.retrieval_run_id, claim.job_id, claim.project_id,
            claim.actor_id, claim.trace_id, "FAILED", 0, None, None,
            error_code, job.completed_at,
        )

    def reconcile_expired_next(
        self, transaction: object,
    ) -> PublishedRAGRetrievalTerminal | None:
        session = self._leases._session(transaction)
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(JobRow).where(
            JobRow.owner_module == "rag",
            JobRow.job_type == "RAG_RETRIEVAL",
            JobRow.scope == "PROJECT",
            JobRow.state == "RUNNING",
            JobRow.lease_expires_at.is_not(None),
            JobRow.lease_expires_at <= now,
        ).order_by(JobRow.lease_expires_at, JobRow.job_id).limit(1)
            .with_for_update(of=JobRow, skip_locked=True)
            .execution_options(populate_existing=True))
        if job is None:
            return None
        lease = session.scalar(select(JobLeaseRow).where(
            JobLeaseRow.job_id == job.job_id,
            JobLeaseRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobLeaseRow).execution_options(populate_existing=True))
        attempt = session.scalar(select(JobAttemptRow).where(
            JobAttemptRow.job_id == job.job_id,
            JobAttemptRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.job_id == job.job_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(populate_existing=True))
        if (lease is None or attempt is None or run is None
                or type(job.project_id) is not uuid.UUID
                or type(job.actor_ref) is not uuid.UUID
                or job.max_attempts != 1 or job.attempt_count != 1
                or job.fencing_token != 1 or job.completed_at is not None
                or job.lease_expires_at != lease.lease_expires_at
                or lease.state != "ACTIVE" or lease.lease_expires_at > now
                or attempt.attempt_no != 1 or attempt.fencing_token != 1
                or attempt.worker_ref != lease.worker_ref
                or attempt.completed_at is not None or attempt.error_code is not None
                or run.retrieval_state != "RUNNING" or run.lock_version != 0
                or run.project_id != job.project_id or run.actor_ref != job.actor_ref
                or str(run.trace_id) != job.trace_id
                or job.payload_refs != {
                    "retrieval_run_id": str(run.retrieval_run_id),
                }):
            raise RAGRetrievalTerminalError()
        try:
            trace_id = uuid.UUID(job.trace_id)
        except (TypeError, ValueError):
            raise RAGRetrievalTerminalError() from None
        lease.state = "EXPIRED"
        attempt.completed_at = now
        attempt.error_code = "RAG_RETRIEVAL_LEASE_EXPIRED"
        job.state = "FAILED"
        job.lease_expires_at = None
        job.completed_at = now
        run.retrieval_state = "FAILED"
        run.rerank_state = "NOT_APPLICABLE"
        run.egress_state = "NOT_APPLICABLE"
        run.quality_flags = []
        run.degraded = False
        run.error_code = "RAG_RETRIEVAL_LEASE_EXPIRED"
        run.completed_at = now
        run.lock_version = 1
        session.flush()
        self._validate_constraints(session)
        return PublishedRAGRetrievalTerminal(
            run.retrieval_run_id, job.job_id, job.project_id, job.actor_ref,
            trace_id, "FAILED", 0, None, None,
            "RAG_RETRIEVAL_LEASE_EXPIRED", now,
        )

    @staticmethod
    def _current_run(run, index, claim: RAGRetrievalClaim,
                     prepared: PreparedRAGRetrieval) -> bool:
        return bool(
            run is not None and index is not None
            and run.retrieval_state == "RUNNING" and run.lock_version == 0
            and run.job_id == claim.job_id and run.project_id == claim.project_id
            and run.actor_ref == claim.actor_id and run.trace_id == claim.trace_id
            and run.project_index_ref == prepared.project_index_ref
            and run.global_index_ref is None
            and run.retrieval_policy_ref == "fts.project.v1"
            and run.rerank_policy_ref == "none.v1"
            and run.top_k == prepared.top_k
            and index.index_state == "ACTIVE" and index.scope == "PROJECT"
            and index.project_id == claim.project_id
            and index.embedding_model_ref == prepared.project_model_ref
        )

    @staticmethod
    def _validate_constraints(session) -> None:
        session.execute(text(f"SET CONSTRAINTS {_CONSTRAINTS} IMMEDIATE"))
        session.execute(text(f"SET CONSTRAINTS {_CONSTRAINTS} DEFERRED"))
