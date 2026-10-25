"""Composition bridge from AI input Owner port to authorized Document reads."""

from __future__ import annotations

import uuid

from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResolutionError, AIInputResolutionQuery, AIInputResourceVersionRef,
    AIResolvedInputVersionRef,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadService,
)


class DocumentVersionAIInputOwner:
    def __init__(self, documents: DocumentReadService) -> None:
        if documents is None:
            raise ValueError("Document read service is required")
        self._documents = documents

    def resolve(
        self, transaction: object, query: AIInputResolutionQuery,
        path_project_id: uuid.UUID, ref: AIInputResourceVersionRef,
    ) -> AIResolvedInputVersionRef:
        if (transaction is None or type(query) is not AIInputResolutionQuery
                or type(ref) is not AIInputResourceVersionRef
                or ref.resource_type != "DOC-02"):
            raise AIInputResolutionError("RESOURCE_NOT_FOUND")
        try:
            identity = self._documents.resolve_version_for_trace(
                transaction, session_token=query.session_token,
                trace_id=query.trace_id, path_project_id=path_project_id,
                document_id=ref.resource_id,
                document_version_id=ref.version_id,
            )
            if (identity.document_id != ref.resource_id
                    or identity.document_version_id != ref.version_id):
                raise AIInputResolutionError("AI_INPUT_UNAVAILABLE")
            return AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION",
                identity.document_id, identity.document_version_id,
                identity.scope, identity.project_id,
            )
        except DocumentReadError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise AIInputResolutionError("LICENSE_OPERATION_DENIED") from None
            if exc.code in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"):
                raise AIInputResolutionError("RESOURCE_NOT_FOUND") from None
            raise AIInputResolutionError("AI_INPUT_UNAVAILABLE") from None
        except AIInputResolutionError:
            raise
        except Exception:
            raise AIInputResolutionError("AI_INPUT_UNAVAILABLE") from None
