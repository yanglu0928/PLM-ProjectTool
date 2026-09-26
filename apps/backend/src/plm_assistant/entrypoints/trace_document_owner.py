"""Composition-layer bridge from Trace owner port to Document authorization."""

from __future__ import annotations

from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadQuery, DocumentReadService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceTargetProof, TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class DocumentVersionTraceOwner:
    def __init__(self, documents: DocumentReadService) -> None:
        if documents is None:
            raise ValueError("Document read service is required")
        self._documents = documents

    def prove(self, transaction: object, query: TraceProofQuery,
              ref: TraceVersionRef) -> TraceTargetProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(ref) is not TraceVersionRef
                or (ref.owner_module, ref.object_type) != ("document", "DOC-02")):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        document_query = DocumentReadQuery(query.session_token, query.trace_id,
                                           ref.scope, ref.project_id)
        try:
            version = self._documents.get_version_for_trace(
                transaction, document_query, ref.object_id, ref.version_id,
            )
        except DocumentReadError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise TraceTargetProofError("LICENSE_OPERATION_DENIED") from None
            if exc.code in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"):
                raise TraceTargetProofError("RESOURCE_NOT_FOUND") from None
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        except Exception:
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        if (version.document_id != ref.object_id
                or version.document_version_id != ref.version_id
                or version.availability_state != "AVAILABLE"):
            raise TraceTargetProofError("TRACE_UNAVAILABLE")
        return TraceTargetProof(ref)
