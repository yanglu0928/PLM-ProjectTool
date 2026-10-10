"""PostgreSQL projection for one immutable, current AI Suggestion."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.application.invocation_read import AIInvocationContextView
from plm_assistant.modules.ai.application.task_read import AITaskInputView
from plm_assistant.modules.ai.application.suggestion_read import (
    AISuggestionEvidenceFact,
    AISuggestionReadError,
    AISuggestionReadRecord,
    AISuggestionSourceFact,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIExecutionContentPlanRow,
    AIExecutionContentSourceRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIInvocationRow,
    AISuggestionEvidenceRefRow,
    AISuggestionPayloadRow,
    AITaskInputRefRow,
    AITaskRow,
)


class SqlAlchemyAISuggestionReadRepository:
    def get(self, transaction: object, *, project_id: uuid.UUID,
            ai_task_id: uuid.UUID) -> AISuggestionReadRecord | None:
        if (type(project_id) is not uuid.UUID or not project_id.int
                or type(ai_task_id) is not uuid.UUID or not ai_task_id.int):
            raise AISuggestionReadError()
        row = _session(transaction).execute(
            select(
                AITaskRow.ai_task_id, AITaskRow.project_id,
                AITaskRow.requested_by, AITaskRow.task_state,
                AITaskRow.suggestion_state, AITaskRow.lock_version,
                AITaskRow.current_invocation_ref,
                AITaskRow.content_plan_ref.label("task_content_plan_ref"),
                AITaskRow.output_schema_ref.label("task_schema_ref"),
                AITaskRow.prompt_template_ref,
                AITaskRow.prompt_version_no.label("task_prompt_version_no"),
                AIInvocationRow.ai_invocation_id,
                AIInvocationRow.ai_provider_id,
                AIInvocationRow.provider_config_version_id,
                AIInvocationRow.ai_model_id,
                AIInvocationRow.model_revision_observed,
                AIInvocationRow.prompt_template_id,
                AIInvocationRow.prompt_version_no,
                AIInvocationRow.output_schema_ref.label("invocation_schema_ref"),
                AIInvocationRow.schema_version.label("invocation_schema_version"),
                AIInvocationRow.content_plan_ref.label("invocation_content_plan_ref"),
                AIInvocationRow.retrieval_run_ref,
                AIInvocationRow.context_bundle_fingerprint.label(
                    "invocation_context_fingerprint"),
                AIInvocationRow.suggestion_payload_ref,
                AIInvocationRow.response_fingerprint,
                AIInvocationRow.invocation_state,
                AIInvocationRow.schema_validation_state,
                AISuggestionPayloadRow.suggestion_payload_id,
                AISuggestionPayloadRow.output_schema_ref.label("payload_schema_ref"),
                AISuggestionPayloadRow.schema_version.label("payload_schema_version"),
                AISuggestionPayloadRow.canonical_payload,
                AISuggestionPayloadRow.payload_fingerprint,
                AISuggestionPayloadRow.fact_status,
                AISuggestionPayloadRow.quality_flags,
                AISuggestionPayloadRow.created_at,
                AIExecutionContentPlanRow.content_plan_id,
                AIExecutionContentPlanRow.content_plan_version,
                AIExecutionContentPlanRow.project_id.label("plan_project_id"),
                AIExecutionContentPlanRow.prompt_template_id.label(
                    "plan_prompt_template_id"),
                AIExecutionContentPlanRow.prompt_version_no.label(
                    "plan_prompt_version_no"),
                AIExecutionContentPlanRow.output_schema_ref.label("plan_schema_ref"),
                AIExecutionContentPlanRow.schema_version.label("plan_schema_version"),
                AIExecutionContentPlanRow.ai_provider_id.label("plan_provider_id"),
                AIExecutionContentPlanRow.provider_config_version_id.label(
                    "plan_provider_config_id"),
                AIExecutionContentPlanRow.ai_model_id.label("plan_model_id"),
                AIExecutionContentPlanRow.model_revision.label("plan_model_revision"),
                AIExecutionContentPlanRow.context_policy_ref,
                AIExecutionContentPlanRow.context_mode,
                AIExecutionContentPlanRow.retrieval_run_id,
                AIExecutionContentPlanRow.context_bundle_id,
                AIExecutionContentPlanRow.context_bundle_fingerprint.label(
                    "plan_context_fingerprint"),
            ).select_from(AITaskRow).join(
                AIInvocationRow,
                AIInvocationRow.ai_invocation_id
                == AITaskRow.current_invocation_ref,
            ).join(
                AISuggestionPayloadRow,
                AISuggestionPayloadRow.suggestion_payload_id
                == AIInvocationRow.suggestion_payload_ref,
            ).join(
                AIExecutionContentPlanRow,
                AIExecutionContentPlanRow.content_plan_id
                == AIInvocationRow.content_plan_ref,
            ).where(
                AITaskRow.scope == "PROJECT",
                AITaskRow.project_id == project_id,
                AITaskRow.ai_task_id == ai_task_id,
            ).execution_options(autoflush=False)
        ).one_or_none()
        if row is None:
            return None
        if (row.task_state != "SUCCEEDED"
                or row.suggestion_state == "NONE"
                or row.current_invocation_ref != row.ai_invocation_id
                or row.invocation_state != "SUCCEEDED"
                or row.schema_validation_state != "VALID"
                or row.suggestion_payload_ref != row.suggestion_payload_id
                or row.task_content_plan_ref != row.content_plan_id
                or row.invocation_content_plan_ref != row.content_plan_id
                or row.plan_project_id != project_id
                or row.task_schema_ref != row.invocation_schema_ref
                or row.task_schema_ref != row.payload_schema_ref
                or row.task_schema_ref != row.plan_schema_ref
                or row.invocation_schema_version != row.payload_schema_version
                or row.invocation_schema_version != row.plan_schema_version
                or row.prompt_template_ref != row.prompt_template_id
                or row.prompt_template_id != row.plan_prompt_template_id
                or row.task_prompt_version_no != row.prompt_version_no
                or row.prompt_version_no != row.plan_prompt_version_no
                or row.ai_provider_id != row.plan_provider_id
                or row.provider_config_version_id != row.plan_provider_config_id
                or row.ai_model_id != row.plan_model_id
                or row.model_revision_observed != row.plan_model_revision
                or row.retrieval_run_ref != row.retrieval_run_id
                or ((row.invocation_context_fingerprint is None)
                    != (row.plan_context_fingerprint is None))
                or row.invocation_context_fingerprint is not None
                and not hmac.compare_digest(
                    row.invocation_context_fingerprint,
                    row.plan_context_fingerprint)):
            raise AISuggestionReadError()
        try:
            canonical = json.dumps(
                row.canonical_payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise AISuggestionReadError() from None
        if (type(row.payload_fingerprint) is not bytes
                or len(row.payload_fingerprint) != 32
                or not hmac.compare_digest(
                    hashlib.sha256(canonical).digest(), row.payload_fingerprint)
                or type(row.response_fingerprint) is not bytes
                or len(row.response_fingerprint) != 32):
            raise AISuggestionReadError()
        quality = row.quality_flags
        if type(quality) is not list:
            raise AISuggestionReadError()
        context = AIInvocationContextView(
            row.content_plan_id, row.content_plan_version,
            row.context_policy_ref, row.context_mode,
            row.retrieval_run_id, row.context_bundle_id,
        )
        input_rows = _session(transaction).execute(
            select(
                AITaskInputRefRow.ref_ordinal,
                AITaskInputRefRow.owner_module,
                AITaskInputRefRow.object_type,
                AITaskInputRefRow.object_id,
                AITaskInputRefRow.version_id,
                AITaskInputRefRow.scope,
                AITaskInputRefRow.project_id,
            ).where(
                AITaskInputRefRow.ai_task_id == row.ai_task_id,
            ).order_by(AITaskInputRefRow.ref_ordinal)
            .execution_options(autoflush=False)
        ).all()
        inputs: list[AITaskInputView] = []
        for position, value in enumerate(input_rows, 1):
            if (value.ref_ordinal != position or value.scope != "PROJECT"
                    or value.project_id != project_id
                    or (value.owner_module, value.object_type)
                    != ("document", "DOCUMENT_VERSION")
                    or type(value.object_id) is not uuid.UUID):
                raise AISuggestionReadError()
            inputs.append(AITaskInputView(
                "DOC-02", value.object_id, value.version_id,
            ))
        evidence_rows = _session(transaction).execute(
            select(
                AISuggestionEvidenceRefRow.ref_ordinal,
                AISuggestionEvidenceRefRow.owner_module,
                AISuggestionEvidenceRefRow.object_type,
                AISuggestionEvidenceRefRow.object_id,
                AISuggestionEvidenceRefRow.version_id,
                AISuggestionEvidenceRefRow.content_fingerprint,
                AISuggestionEvidenceRefRow.project_id,
                AISuggestionEvidenceRefRow.scope,
            ).where(
                AISuggestionEvidenceRefRow.suggestion_payload_id
                == row.suggestion_payload_id,
            ).order_by(AISuggestionEvidenceRefRow.ref_ordinal)
            .execution_options(autoflush=False)
        ).all()
        evidence: list[AISuggestionEvidenceFact] = []
        for value in evidence_rows:
            if value.scope != "PROJECT" or value.project_id != project_id:
                raise AISuggestionReadError()
            evidence.append(AISuggestionEvidenceFact(
                value.ref_ordinal, value.owner_module, value.object_type,
                value.object_id, value.version_id, value.content_fingerprint,
            ))
        source_rows = _session(transaction).execute(
            select(
                AIExecutionContentSourceRow.source_ordinal,
                AIExecutionContentSourceRow.resource_type,
                AIExecutionContentSourceRow.owner_module,
                AIExecutionContentSourceRow.object_type,
                AIExecutionContentSourceRow.object_id,
                AIExecutionContentSourceRow.version_id,
                AIExecutionContentSourceRow.project_id,
                AIExecutionContentSourceRow.content_revision_id,
                AIExecutionContentSourceRow.content_object_id,
                AIExecutionContentSourceRow.source_fingerprint,
                AIExecutionContentSourceRow.content_fingerprint,
            ).where(
                AIExecutionContentSourceRow.content_plan_id == row.content_plan_id,
            ).order_by(AIExecutionContentSourceRow.source_ordinal)
            .execution_options(autoflush=False)
        ).all()
        sources = tuple(AISuggestionSourceFact(
            value.source_ordinal, value.resource_type, value.owner_module,
            value.object_type, value.object_id, value.version_id,
            value.project_id, value.content_revision_id, value.content_object_id,
            value.source_fingerprint, value.content_fingerprint,
        ) for value in source_rows)
        return AISuggestionReadRecord(
            row.ai_task_id, row.project_id, row.requested_by,
            row.task_state, row.suggestion_state, row.lock_version,
            row.ai_invocation_id, row.suggestion_payload_id,
            row.content_plan_id, tuple(inputs),
            row.ai_provider_id, row.provider_config_version_id,
            row.ai_model_id, row.model_revision_observed,
            row.prompt_template_id, row.prompt_version_no,
            row.payload_schema_ref, row.payload_schema_version,
            context, row.canonical_payload, canonical,
            row.payload_fingerprint, row.fact_status,
            tuple(quality), row.created_at, tuple(evidence), sources,
        )
