"""Fail-closed PostgreSQL projections for project RetrievalRun reads."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select

from plm_assistant.modules.document.infrastructure.orm import DocumentRow, DocumentVersionRow
from plm_assistant.modules.rag.application.retrieval_read import (
    RAGContextBundleView,
    RAGContextItemView,
    RAGRetrievalCandidateView,
    RAGRetrievalReadError,
    RAGRetrievalResultView,
    RAGRetrievalRunView,
    RAGRetrievalScorePartView,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    ContextBundleRow,
    ContextItemRow,
    DocumentChunkRow,
    RetrievalCandidateRow,
    RetrievalRunRow,
    RetrievalScorePartRow,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_preparation_repository import (
    _session,
)


class SqlAlchemyRAGRetrievalReadRepository:
    def get_run(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                project_id: uuid.UUID) -> RAGRetrievalRunView | None:
        if not self._ids(retrieval_run_id, project_id):
            return None
        row = _session(transaction).execute(select(
            RetrievalRunRow.retrieval_run_id, RetrievalRunRow.project_id,
            RetrievalRunRow.actor_ref,
            RetrievalRunRow.global_index_ref, RetrievalRunRow.project_index_ref,
            RetrievalRunRow.retrieval_policy_ref, RetrievalRunRow.rerank_policy_ref,
            RetrievalRunRow.top_k, RetrievalRunRow.rerank_state,
            RetrievalRunRow.egress_state, RetrievalRunRow.retrieval_state,
            RetrievalRunRow.quality_flags, RetrievalRunRow.degraded,
            RetrievalRunRow.error_code, RetrievalRunRow.job_id,
            RetrievalRunRow.trace_id, RetrievalRunRow.lock_version,
            RetrievalRunRow.created_at, RetrievalRunRow.completed_at,
        ).where(
            RetrievalRunRow.retrieval_run_id == retrieval_run_id,
            RetrievalRunRow.scope == "PROJECT",
            RetrievalRunRow.project_id == project_id,
        ).with_for_update(read=True, of=RetrievalRunRow)
          .execution_options(populate_existing=True, autoflush=False)).one_or_none()
        if row is None or type(row.project_index_ref) is not uuid.UUID:
            return None
        return RAGRetrievalRunView(
            row.retrieval_run_id, row.project_id, row.actor_ref,
            row.global_index_ref, row.project_index_ref, row.retrieval_policy_ref,
            row.rerank_policy_ref, row.top_k, row.rerank_state,
            row.egress_state, row.retrieval_state, tuple(row.quality_flags),
            row.degraded, row.error_code, row.job_id, row.trace_id,
            row.lock_version, row.created_at, row.completed_at,
        )

    def get_result(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                   project_id: uuid.UUID) -> RAGRetrievalResultView | None:
        material = self._successful_material(
            transaction, retrieval_run_id=retrieval_run_id,
            project_id=project_id,
        )
        if material is None:
            return None
        run, _bundle, rows = material
        session = _session(transaction)
        candidate_ids = tuple(row[0].candidate_id for row in rows)
        score_rows = session.execute(select(RetrievalScorePartRow).where(
            RetrievalScorePartRow.retrieval_run_id == retrieval_run_id,
            RetrievalScorePartRow.project_id == project_id,
            RetrievalScorePartRow.candidate_id.in_(candidate_ids),
        ).order_by(
            RetrievalScorePartRow.candidate_id,
            RetrievalScorePartRow.score_ordinal,
            RetrievalScorePartRow.score_part_id,
        ).execution_options(autoflush=False)).scalars().all()
        scores: dict[uuid.UUID, list[RAGRetrievalScorePartView]] = {
            item: [] for item in candidate_ids
        }
        for score in score_rows:
            if score.candidate_id not in scores:
                return None
            scores[score.candidate_id].append(RAGRetrievalScorePartView(
                score.score_kind, score.score_ordinal, score.raw_score_micros,
                score.normalized_score_micros, score.weight_micros,
                score.weighted_score_micros, score.score_policy_ref,
            ))
        candidates: list[RAGRetrievalCandidateView] = []
        for candidate, item, chunk, _version, _document in rows:
            parts = tuple(scores[candidate.candidate_id])
            if not parts:
                return None
            snippet = chunk.search_body[item.snippet_start:item.snippet_end]
            candidates.append(RAGRetrievalCandidateView(
                candidate.candidate_id, candidate.candidate_ordinal,
                candidate.chunk_id, candidate.document_version_ref,
                candidate.parse_result_ref, candidate.source_type,
                dict(candidate.source_locator), candidate.retrieval_channel,
                candidate.final_score_micros, parts, snippet,
            ))
        return RAGRetrievalResultView(
            run.retrieval_run_id, run.project_id, tuple(candidates),
            tuple(run.quality_flags), run.degraded, run.completed_at,
        )

    def get_context(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                    project_id: uuid.UUID) -> RAGContextBundleView | None:
        material = self._successful_material(
            transaction, retrieval_run_id=retrieval_run_id,
            project_id=project_id,
        )
        if material is None:
            return None
        run, bundle, rows = material
        items = tuple(RAGContextItemView(
            item.item_ordinal, item.chunk_id, item.document_version_ref,
            dict(item.source_locator), item.snippet_start, item.snippet_end,
            item.token_count,
            chunk.search_body[item.snippet_start:item.snippet_end],
        ) for _candidate, item, chunk, _version, _document in rows)
        return RAGContextBundleView(
            bundle.context_bundle_id, run.retrieval_run_id, run.project_id,
            bundle.context_policy_ref, bytes(bundle.bundle_fingerprint),
            bundle.token_budget, bundle.token_count, items, bundle.created_at,
        )

    def _successful_material(self, transaction: object, *,
                             retrieval_run_id: uuid.UUID,
                             project_id: uuid.UUID):
        if not self._ids(retrieval_run_id, project_id):
            return None
        session = _session(transaction)
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.retrieval_run_id == retrieval_run_id,
            RetrievalRunRow.scope == "PROJECT",
            RetrievalRunRow.project_id == project_id,
        ).with_for_update(read=True, of=RetrievalRunRow)
          .execution_options(populate_existing=True, autoflush=False))
        bundle = session.scalar(select(ContextBundleRow).where(
            ContextBundleRow.retrieval_run_id == retrieval_run_id,
            ContextBundleRow.project_id == project_id,
            ContextBundleRow.context_policy_ref == "project-documents.v1",
        ).execution_options(populate_existing=True, autoflush=False))
        if (run is None or bundle is None
                or run.retrieval_state != "SUCCEEDED"
                or run.error_code is not None or run.completed_at is None
                or bundle.item_count < 1):
            return None
        rows = session.execute(select(
            RetrievalCandidateRow, ContextItemRow, DocumentChunkRow,
            DocumentVersionRow, DocumentRow,
        ).join(
            ContextItemRow,
            (ContextItemRow.candidate_id == RetrievalCandidateRow.candidate_id)
            & (ContextItemRow.retrieval_run_id
               == RetrievalCandidateRow.retrieval_run_id),
        ).join(
            DocumentChunkRow,
            DocumentChunkRow.chunk_id == RetrievalCandidateRow.chunk_id,
        ).join(
            DocumentVersionRow,
            DocumentVersionRow.document_version_id
            == RetrievalCandidateRow.document_version_ref,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).where(
            RetrievalCandidateRow.retrieval_run_id == retrieval_run_id,
            RetrievalCandidateRow.run_project_id == project_id,
            ContextItemRow.context_bundle_id == bundle.context_bundle_id,
            ContextItemRow.project_id == project_id,
        ).order_by(RetrievalCandidateRow.candidate_ordinal)
          .with_for_update(
              read=True, of=(DocumentChunkRow, DocumentVersionRow, DocumentRow),
          ).execution_options(populate_existing=True, autoflush=False)).all()
        if (len(rows) != bundle.item_count
                or tuple(row[0].candidate_ordinal for row in rows)
                   != tuple(range(bundle.item_count))
                or tuple(row[1].item_ordinal for row in rows)
                   != tuple(range(bundle.item_count))):
            return None
        token_count = 0
        for candidate, item, chunk, version, document in rows:
            snippet = chunk.search_body[item.snippet_start:item.snippet_end]
            if (candidate.candidate_scope != "PROJECT"
                    or candidate.candidate_project_id != project_id
                    or candidate.run_project_id != project_id
                    or candidate.chunk_id != item.chunk_id
                    or candidate.document_version_ref != item.document_version_ref
                    or candidate.source_locator != item.source_locator
                    or candidate.authorization_snapshot_fingerprint
                       != item.access_snapshot_fingerprint
                    or chunk.scope != "PROJECT" or chunk.project_id != project_id
                    or chunk.chunk_state != "ACTIVE"
                    or chunk.document_version_ref != item.document_version_ref
                    or version.scope != "PROJECT" or version.project_id != project_id
                    or version.availability_state != "AVAILABLE"
                    or document.scope != "PROJECT" or document.project_id != project_id
                    or document.document_state != "ACTIVE"
                    or not snippet
                    or hashlib.sha256(snippet.encode("utf-8")).digest()
                       != bytes(item.snippet_fingerprint)
                    or len(snippet) != item.token_count):
                return None
            token_count += item.token_count
        if token_count != bundle.token_count:
            return None
        return run, bundle, rows

    @staticmethod
    def _ids(*values: object) -> bool:
        return all(type(value) is uuid.UUID and value.int for value in values)
