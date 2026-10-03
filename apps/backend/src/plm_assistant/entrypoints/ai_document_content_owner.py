"""Anti-corruption adapter from AI content plans to Document-owned text."""

from __future__ import annotations

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentIdentityQuery,
    AIExecutionContentPlanError,
    AIExecutionContentProjection,
    AIExecutionContentReadQuery,
    AIExecutionContentSourceIdentity,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionInputRef,
)
from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentError,
    DocumentAIContentIdentity,
    DocumentAIContentQuery,
    DocumentAIContentService,
)


class AIDocumentContentOwner:
    def __init__(self, service: DocumentAIContentService) -> None:
        if type(service) is not DocumentAIContentService:
            raise ValueError("Document AI content service required")
        self._service = service

    def resolve_identity(
        self, transaction: object, query: AIExecutionContentIdentityQuery,
        input_ref: AITaskExecutionInputRef,
    ) -> AIExecutionContentSourceIdentity:
        if (type(query) is not AIExecutionContentIdentityQuery
                or type(input_ref) is not AITaskExecutionInputRef
                or not self._supports(input_ref)
                or input_ref.project_id != query.project_id):
            raise AIExecutionContentPlanError()
        try:
            identity = self._service.resolve_identity(
                transaction,
                query=DocumentAIContentQuery(
                    query.project_id, query.requested_by, query.trace_id,
                    query.purpose_ref, query.minimal_payload_policy_ref,
                    "document.parse.fixed.v1",
                ),
                document_id=input_ref.object_id,
                document_version_id=input_ref.version_id,
            )
            return self._to_ai(input_ref.ordinal, identity)
        except DocumentAIContentError:
            raise AIExecutionContentPlanError(
                "AI_EXECUTION_SOURCE_UNAVAILABLE") from None

    def read_exact(
        self, transaction: object, query: AIExecutionContentReadQuery,
        source: AIExecutionContentSourceIdentity,
    ) -> AIExecutionContentProjection:
        if (type(query) is not AIExecutionContentReadQuery
                or type(source) is not AIExecutionContentSourceIdentity
                or source.project_id != query.project_id
                or source.resource_type != "DOC-02"
                or source.owner_module != "document"
                or source.object_type != "DOCUMENT_VERSION"
                or source.content_kind != "DOCUMENT_PARSED_TEXT"
                or source.content_schema_ref != "document.parse-result.v1"
                or source.selection_policy_ref != "document.parse.fixed.v1"):
            raise AIExecutionContentPlanError(
                "AI_EXECUTION_SOURCE_UNAVAILABLE")
        try:
            identity = DocumentAIContentIdentity(
                source.object_id, source.version_id, source.project_id,
                source.content_revision_id, source.content_object_id,
                source.producer_ref, source.producer_version,
                source.selection_policy_ref, source.source_fingerprint,
            source.content_fingerprint, source.projection_fingerprint,
            source.content_size_bytes,
                source.record_count,
            )
            result = self._service.read_exact(
                transaction,
                query=DocumentAIContentQuery(
                    query.project_id, query.requested_by, query.trace_id,
                    query.purpose_ref, query.minimal_payload_policy_ref,
                    source.selection_policy_ref,
                ),
                identity=identity,
            )
            return AIExecutionContentProjection(
                source, result.projection_schema_ref,
                result.identity.record_count, result.content_utf8,
            )
        except DocumentAIContentError:
            raise AIExecutionContentPlanError(
                "AI_EXECUTION_SOURCE_UNAVAILABLE") from None

    @staticmethod
    def _supports(input_ref: AITaskExecutionInputRef) -> bool:
        return (input_ref.resource_type == "DOC-02"
                and input_ref.owner_module == "document"
                and input_ref.object_type == "DOCUMENT_VERSION")

    @staticmethod
    def _to_ai(
        ordinal: int, identity: DocumentAIContentIdentity,
    ) -> AIExecutionContentSourceIdentity:
        return AIExecutionContentSourceIdentity(
            ordinal, "DOC-02", "document", "DOCUMENT_VERSION",
            identity.document_id, identity.document_version_id,
            identity.project_id, "DOCUMENT_PARSED_TEXT",
            identity.parse_record_id, identity.result_ref_id,
            identity.parser_profile, identity.parser_version,
            "document.parse-result.v1", identity.selection_policy_ref,
            identity.source_sha256, identity.result_sha256,
            identity.projection_sha256, identity.result_size_bytes,
            identity.record_count,
        )
