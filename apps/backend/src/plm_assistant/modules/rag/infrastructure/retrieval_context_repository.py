"""PostgreSQL projection of one immutable minimum RAG Context bundle."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from plm_assistant.modules.document.infrastructure.orm import DocumentRow, DocumentVersionRow
from plm_assistant.modules.rag.application.retrieval_context import (
    RAGContextProjection,
    RAGContextReadError,
    RAGContextReadRequest,
)
from plm_assistant.modules.rag.application.retrieval_terminal import (
    context_bundle_fingerprint,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    ContextBundleRow,
    ContextItemRow,
    DocumentChunkRow,
    RetrievalCandidateRow,
    RetrievalRunRow,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_preparation_repository import (
    _session,
)


class SqlAlchemyRAGContextRepository:
    def read_exact(self, transaction: object, *, request: RAGContextReadRequest
                   ) -> RAGContextProjection | None:
        if type(request) is not RAGContextReadRequest:
            raise RAGContextReadError("VALIDATION_FAILED")
        request.__post_init__()
        session = _session(transaction)
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.retrieval_run_id == request.retrieval_run_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(populate_existing=True))
        bundle = session.scalar(select(ContextBundleRow).where(
            ContextBundleRow.context_bundle_id == request.context_bundle_id,
            ContextBundleRow.retrieval_run_id == request.retrieval_run_id,
        ).execution_options(populate_existing=True))
        if (run is None or bundle is None
                or run.scope != "PROJECT" or run.project_id != request.project_id
                or run.retrieval_state != "SUCCEEDED" or run.error_code is not None
                or run.degraded or run.completed_at is None
                or bundle.project_id != request.project_id
                or bundle.context_policy_ref != "project-documents.v1"
                or bytes(bundle.bundle_fingerprint)
                   != request.context_bundle_fingerprint
                or bundle.item_count != request.record_count):
            return None
        rows = session.execute(select(
            ContextItemRow, RetrievalCandidateRow, DocumentChunkRow,
            DocumentVersionRow, DocumentRow,
        ).join(
            RetrievalCandidateRow,
            RetrievalCandidateRow.candidate_id == ContextItemRow.candidate_id,
        ).join(
            DocumentChunkRow, DocumentChunkRow.chunk_id == ContextItemRow.chunk_id,
        ).join(
            DocumentVersionRow,
            DocumentVersionRow.document_version_id
            == ContextItemRow.document_version_ref,
        ).join(
            DocumentRow, DocumentRow.document_id == DocumentVersionRow.document_id,
        ).where(
            ContextItemRow.context_bundle_id == request.context_bundle_id,
            ContextItemRow.retrieval_run_id == request.retrieval_run_id,
        ).order_by(ContextItemRow.item_ordinal).with_for_update(
            of=(DocumentChunkRow, DocumentVersionRow, DocumentRow),
        ).execution_options(populate_existing=True)).all()
        if (len(rows) != bundle.item_count
                or [row[0].item_ordinal for row in rows]
                   != list(range(bundle.item_count))):
            return None
        facts = []
        payload_items = []
        token_count = 0
        for item, candidate, chunk, version, document in rows:
            if (item.project_id != request.project_id
                    or candidate.retrieval_run_id != request.retrieval_run_id
                    or candidate.candidate_ordinal != item.item_ordinal
                    or candidate.candidate_scope != "PROJECT"
                    or candidate.candidate_project_id != request.project_id
                    or candidate.run_project_id != request.project_id
                    or candidate.chunk_id != item.chunk_id
                    or candidate.document_version_ref != item.document_version_ref
                    or candidate.source_locator != item.source_locator
                    or candidate.authorization_snapshot_fingerprint
                       != item.access_snapshot_fingerprint
                    or chunk.scope != "PROJECT" or chunk.project_id != request.project_id
                    or chunk.chunk_state != "ACTIVE"
                    or chunk.document_version_ref != item.document_version_ref
                    or version.scope != "PROJECT" or version.project_id != request.project_id
                    or version.availability_state != "AVAILABLE"
                    or document.scope != "PROJECT"
                    or document.project_id != request.project_id
                    or document.document_state != "ACTIVE"):
                return None
            snippet = chunk.search_body[item.snippet_start:item.snippet_end]
            encoded = snippet.encode("utf-8")
            if (not snippet
                    or hashlib.sha256(encoded).digest()
                       != bytes(item.snippet_fingerprint)
                    or item.token_count != len(snippet)):
                return None
            token_count += item.token_count
            facts.append((
                item.item_ordinal, candidate.candidate_id, item.chunk_id,
                bytes(item.snippet_fingerprint),
                bytes(item.access_snapshot_fingerprint),
            ))
            payload_items.append({
                "document_version_id": str(item.document_version_ref),
                "node_id": str(item.chunk_id),
                "ordinal": item.item_ordinal,
                "source_locator": dict(item.source_locator),
                "text": snippet,
            })
        if (token_count != bundle.token_count
                or context_bundle_fingerprint(
                    retrieval_run_id=request.retrieval_run_id,
                    project_id=request.project_id,
                    item_facts=tuple(facts),
                ) != bytes(bundle.bundle_fingerprint)):
            return None
        content = json.dumps({
            "context_bundle_id": str(bundle.context_bundle_id),
            "items": payload_items,
            "retrieval_run_id": str(run.retrieval_run_id),
            "schema_version": "rag-context-minimum-text.v1",
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
           allow_nan=False).encode("utf-8")
        if len(content) != request.content_size_bytes:
            return None
        return RAGContextProjection(
            run.retrieval_run_id, bundle.context_bundle_id,
            bytes(bundle.bundle_fingerprint), bundle.item_count, content,
        )
