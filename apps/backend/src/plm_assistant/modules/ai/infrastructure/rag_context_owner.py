"""Adapter from AI execution Context identity to the RAG Context Owner."""

from __future__ import annotations

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentReadQuery,
    AIExecutionContextIdentity,
)
from plm_assistant.modules.rag.application.retrieval_context import (
    RAGContextReadRequest,
    RAGContextReadService,
)


class AIRAGContextReadOwner:
    def __init__(self, service: RAGContextReadService) -> None:
        if service is None:
            raise ValueError("RAG Context read service required")
        self._service = service

    def read_exact(self, transaction: object,
                   query: AIExecutionContentReadQuery,
                   context: AIExecutionContextIdentity) -> str:
        if (transaction is None
                or type(query) is not AIExecutionContentReadQuery
                or type(context) is not AIExecutionContextIdentity
                or context.mode != "RAG_CONTEXT"
                or context.retrieval_run_id is None
                or context.context_bundle_id is None
                or context.context_bundle_fingerprint is None):
            raise RuntimeError("AI RAG Context is unavailable")
        query.__post_init__()
        context.__post_init__()
        projection = self._service.read_exact(transaction, request=RAGContextReadRequest(
            query.project_id, query.requested_by, query.trace_id,
            context.retrieval_run_id, context.context_bundle_id,
            context.context_bundle_fingerprint, context.record_count,
            context.content_size_bytes,
        ))
        return projection.content_utf8.decode("utf-8")
