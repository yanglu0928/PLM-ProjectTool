"""PostgreSQL projection of complete, non-content AI execution metadata."""

from __future__ import annotations

import uuid

from sqlalchemy import Text, cast, func, select

from plm_assistant.modules.ai.application.create_task import input_refs_fingerprint
from plm_assistant.modules.ai.application.input_resolution import AIResolvedInputVersionRef
from plm_assistant.modules.ai.application.task_execution_grant import AITaskExecutionInputRef
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantMaterial,
)
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptTemplateRow, PromptVersionRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow, AITaskInputRefRow, AITaskRow,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
)


_RESOURCE_TYPES = {("document", "DOCUMENT_VERSION"): "DOC-02"}


def _bytes32(value: object) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise RuntimeError("invalid AI execution metadata")
    return value


def _categories(value: object) -> tuple[str, ...]:
    if (type(value) is not list or not 1 <= len(value) <= 64
            or len(set(value)) != len(value)
            or any(type(item) is not str for item in value)):
        raise RuntimeError("invalid AI execution metadata")
    return tuple(value)


class SqlAlchemyAITaskExecutionGrantRepository:
    def load(self, transaction: object, *, claim: AITaskExecutionClaim,
             now) -> AITaskExecutionGrantMaterial | None:
        if type(claim) is not AITaskExecutionClaim:
            return None
        claim.__post_init__()
        session = _session(transaction)
        parameters_text = cast(AITaskRow.task_parameters, Text)
        row = session.execute(select(
            AITaskRow.ai_task_id, AITaskRow.project_id, AITaskRow.job_ref,
            AITaskRow.requested_by, AITaskRow.trace_id, AITaskRow.task_type,
            AITaskRow.input_fingerprint, AITaskRow.prompt_policy_ref,
            AITaskRow.prompt_policy_version, AITaskRow.prompt_template_ref,
            AITaskRow.prompt_version_no, AITaskRow.output_schema_ref,
            AITaskRow.context_policy_ref, AITaskRow.task_parameters_fingerprint,
            AITaskRow.content_plan_ref,
            PromptVersionRow.system_template_hash,
            PromptVersionRow.user_template_hash,
            PromptVersionRow.provider_policy_ref,
            PromptVersionRow.schema_version,
            AIEgressAuthorizationSnapshotRow.egress_authorization_snapshot_id,
            AIEgressAuthorizationSnapshotRow.authorization_ref,
            AIEgressAuthorizationSnapshotRow.authorization_fingerprint,
            AIEgressAuthorizationSnapshotRow.purpose_ref,
            AIEgressAuthorizationSnapshotRow.ai_provider_id,
            AIEgressAuthorizationSnapshotRow.provider_config_version_id,
            AIEgressAuthorizationSnapshotRow.ai_model_id,
            AIEgressAuthorizationSnapshotRow.data_region,
            AIEgressAuthorizationSnapshotRow.allowed_data_categories,
            AIEgressAuthorizationSnapshotRow.preview_payload_fingerprint,
            AIEgressAuthorizationSnapshotRow.source_refs_fingerprint,
            AIEgressAuthorizationSnapshotRow.approved_by,
            AIEgressAuthorizationSnapshotRow.approved_role,
            AIEgressAuthorizationSnapshotRow.approved_at,
            AIEgressAuthorizationSnapshotRow.valid_until,
            AIEgressAuthorizationSnapshotRow.max_payload_bytes,
            AIEgressAuthorizationSnapshotRow.max_input_tokens,
            AIEgressAuthorizationSnapshotRow.max_retry_attempts,
            AIEgressAuthorizationSnapshotRow.content_plan_ref.label(
                "snapshot_content_plan_ref"),
            AIModelRow.provider_model_key, AIModelRow.model_revision,
        ).join(
            PromptTemplateRow,
            PromptTemplateRow.prompt_template_id == AITaskRow.prompt_template_ref,
        ).join(
            PromptVersionRow,
            (PromptVersionRow.prompt_template_id == AITaskRow.prompt_template_ref)
            & (PromptVersionRow.version_no == AITaskRow.prompt_version_no),
        ).join(
            AIEgressAuthorizationSnapshotRow,
            AIEgressAuthorizationSnapshotRow.ai_task_id == AITaskRow.ai_task_id,
        ).join(
            AIModelRow,
            (AIModelRow.ai_model_id == AIEgressAuthorizationSnapshotRow.ai_model_id)
            & (AIModelRow.ai_provider_id
               == AIEgressAuthorizationSnapshotRow.ai_provider_id),
        ).where(
            AITaskRow.ai_task_id == claim.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == claim.project_id,
            AITaskRow.job_ref == claim.job_id,
            AITaskRow.requested_by == claim.actor_id,
            AITaskRow.trace_id == claim.trace_id,
            AITaskRow.input_fingerprint == claim.input_fingerprint,
            AITaskRow.task_state == "QUEUED",
            AITaskRow.current_invocation_ref.is_(None),
            AITaskRow.started_at.is_(None),
            AITaskRow.prompt_template_ref.is_not(None),
            AITaskRow.prompt_version_no.is_not(None),
            AITaskRow.prompt_policy_version.is_not(None),
            AITaskRow.task_parameters.is_not(None),
            AITaskRow.task_parameters_fingerprint.is_not(None),
            AITaskRow.content_plan_ref.is_not(None),
            AITaskRow.task_parameters_fingerprint
            == func.sha256(func.convert_to(parameters_text, "UTF8")),
            PromptTemplateRow.task_type == AITaskRow.task_type,
            PromptTemplateRow.scope == "DEPLOYMENT",
            PromptTemplateRow.template_state == "ACTIVE",
            PromptTemplateRow.active_version_no == AITaskRow.prompt_version_no,
            PromptVersionRow.output_schema_ref == AITaskRow.output_schema_ref,
            PromptVersionRow.rag_policy_ref == AITaskRow.context_policy_ref,
            AIEgressAuthorizationSnapshotRow.scope == "PROJECT",
            AIEgressAuthorizationSnapshotRow.project_id == claim.project_id,
            AIEgressAuthorizationSnapshotRow.authorization_ref
            == claim.egress_authorization_ref,
            AIEgressAuthorizationSnapshotRow.authorization_state_at_capture
            == "AUTHORIZED",
            AIEgressAuthorizationSnapshotRow.source_refs_fingerprint
            == claim.input_fingerprint,
            AIEgressAuthorizationSnapshotRow.ai_model_id.is_not(None),
            AIEgressAuthorizationSnapshotRow.content_plan_ref
            == AITaskRow.content_plan_ref,
            AIEgressAuthorizationSnapshotRow.valid_until > now,
            AIModelRow.model_kind == "CHAT",
            AIModelRow.model_state == "AVAILABLE",
        ).with_for_update(of=AITaskRow)
          .execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None

        input_rows = list(session.execute(select(
            AITaskInputRefRow.ref_ordinal, AITaskInputRefRow.scope,
            AITaskInputRefRow.project_id, AITaskInputRefRow.owner_module,
            AITaskInputRefRow.object_type, AITaskInputRefRow.object_id,
            AITaskInputRefRow.version_id,
        ).where(
            AITaskInputRefRow.ai_task_id == claim.ai_task_id,
        ).order_by(AITaskInputRefRow.ref_ordinal)
          .execution_options(autoflush=False)))
        if not 1 <= len(input_rows) <= 1000:
            return None
        refs: list[AITaskExecutionInputRef] = []
        resolved: list[AIResolvedInputVersionRef] = []
        for ordinal, item in enumerate(input_rows, 1):
            resource_type = _RESOURCE_TYPES.get((item.owner_module, item.object_type))
            if (item.ref_ordinal != ordinal or resource_type is None
                    or item.scope != "PROJECT" or item.project_id != claim.project_id
                    or type(item.object_id) is not uuid.UUID or not item.object_id.int
                    or type(item.version_id) is not uuid.UUID or not item.version_id.int):
                return None
            refs.append(AITaskExecutionInputRef(
                ordinal, resource_type, item.owner_module, item.object_type,
                item.object_id, item.version_id, item.project_id,
            ))
            resolved.append(AIResolvedInputVersionRef(
                resource_type, item.owner_module, item.object_type,
                item.object_id, item.version_id, item.scope, item.project_id,
            ))
        source_fingerprint = _bytes32(row.input_fingerprint)
        if input_refs_fingerprint(tuple(resolved)) != source_fingerprint:
            return None
        return AITaskExecutionGrantMaterial(
            row.ai_task_id, row.project_id, row.job_ref, row.requested_by,
            row.trace_id, row.task_type, tuple(refs), source_fingerprint,
            row.prompt_policy_ref, row.prompt_policy_version,
            row.prompt_template_ref, row.prompt_version_no,
            row.system_template_hash, row.user_template_hash,
            row.provider_policy_ref, row.output_schema_ref,
            row.schema_version, row.context_policy_ref,
            _bytes32(row.task_parameters_fingerprint),
            row.egress_authorization_snapshot_id, row.authorization_ref,
            _bytes32(row.authorization_fingerprint), row.purpose_ref,
            row.ai_provider_id, row.provider_config_version_id,
            row.ai_model_id, row.provider_model_key, row.model_revision,
            row.data_region, _categories(row.allowed_data_categories),
            _bytes32(row.preview_payload_fingerprint), row.approved_by,
            row.approved_role, row.approved_at, row.max_payload_bytes,
            row.max_input_tokens, row.max_retry_attempts, row.valid_until,
            row.content_plan_ref,
        )
