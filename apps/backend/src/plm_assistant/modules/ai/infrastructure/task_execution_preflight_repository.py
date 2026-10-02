"""PostgreSQL projection for AI Task execution admission."""

from __future__ import annotations

import uuid

from sqlalchemy import Text, cast, func, select

from plm_assistant.modules.ai.application.task_execution_preflight import (
    AITaskExecutionSnapshot,
)
from plm_assistant.modules.ai.infrastructure.prompt_orm import PromptVersionRow
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow, AITaskRow,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow


class SqlAlchemyAITaskExecutionSnapshotRepository:
    def load_for_execution(self, transaction: object, *, ai_task_id: uuid.UUID,
                           project_id: uuid.UUID,
                           job_id: uuid.UUID) -> AITaskExecutionSnapshot | None:
        if any(type(value) is not uuid.UUID or not value.int
               for value in (ai_task_id, project_id, job_id)):
            return None
        parameters_text = cast(AITaskRow.task_parameters, Text)
        row = _session(transaction).execute(select(
            AITaskRow.ai_task_id, AITaskRow.project_id, AITaskRow.job_ref,
            AITaskRow.task_type, AITaskRow.input_fingerprint,
            AITaskRow.prompt_policy_ref, AITaskRow.prompt_policy_version,
            AITaskRow.prompt_template_ref, AITaskRow.prompt_version_no,
            AITaskRow.output_schema_ref, AITaskRow.context_policy_ref,
            AITaskRow.task_parameters, AITaskRow.task_parameters_fingerprint,
            AIEgressAuthorizationSnapshotRow.authorization_ref,
            AIEgressAuthorizationSnapshotRow.authorization_fingerprint,
            AIEgressAuthorizationSnapshotRow.purpose_ref,
            AIEgressAuthorizationSnapshotRow.ai_provider_id,
            AIEgressAuthorizationSnapshotRow.provider_config_version_id,
            AIEgressAuthorizationSnapshotRow.ai_model_id,
            AIEgressAuthorizationSnapshotRow.valid_until,
        ).join(
            JobRow, JobRow.job_id == AITaskRow.job_ref,
        ).join(
            PromptVersionRow,
            (PromptVersionRow.prompt_template_id == AITaskRow.prompt_template_ref)
            & (PromptVersionRow.version_no == AITaskRow.prompt_version_no),
        ).join(
            AIEgressAuthorizationSnapshotRow,
            AIEgressAuthorizationSnapshotRow.ai_task_id == AITaskRow.ai_task_id,
        ).where(
            AITaskRow.ai_task_id == ai_task_id,
            AITaskRow.scope == "PROJECT", AITaskRow.project_id == project_id,
            AITaskRow.job_ref == job_id, AITaskRow.task_state == "QUEUED",
            AITaskRow.prompt_template_ref.is_not(None),
            AITaskRow.prompt_version_no.is_not(None),
            AITaskRow.prompt_policy_version.is_not(None),
            AITaskRow.task_parameters.is_not(None),
            AITaskRow.task_parameters_fingerprint.is_not(None),
            AITaskRow.task_parameters_fingerprint
            == func.sha256(func.convert_to(parameters_text, "UTF8")),
            PromptVersionRow.output_schema_ref == AITaskRow.output_schema_ref,
            PromptVersionRow.rag_policy_ref == AITaskRow.context_policy_ref,
            JobRow.owner_module == "ai", JobRow.job_type == "AI_TASK_EXECUTE",
            JobRow.scope == "PROJECT", JobRow.project_id == project_id,
            JobRow.state == "PENDING",
            JobRow.payload_refs["ai_task_id"].astext == str(ai_task_id),
            AIEgressAuthorizationSnapshotRow.scope == "PROJECT",
            AIEgressAuthorizationSnapshotRow.project_id == project_id,
            AIEgressAuthorizationSnapshotRow.authorization_state_at_capture == "AUTHORIZED",
            AIEgressAuthorizationSnapshotRow.source_refs_fingerprint
            == AITaskRow.input_fingerprint,
            AIEgressAuthorizationSnapshotRow.ai_model_id.is_not(None),
        ).with_for_update(of=AITaskRow)
          .execution_options(autoflush=False)).one_or_none()
        if row is None or type(row.task_parameters) is not dict:
            return None
        return AITaskExecutionSnapshot(
            row.ai_task_id, row.project_id, row.job_ref, row.task_type,
            bytes(row.input_fingerprint), row.prompt_policy_ref,
            row.prompt_policy_version, row.prompt_template_ref,
            row.prompt_version_no, row.output_schema_ref,
            row.context_policy_ref, dict(row.task_parameters),
            bytes(row.task_parameters_fingerprint), row.authorization_ref,
            bytes(row.authorization_fingerprint), row.purpose_ref,
            row.ai_provider_id, row.provider_config_version_id, row.ai_model_id,
            row.valid_until,
        )
