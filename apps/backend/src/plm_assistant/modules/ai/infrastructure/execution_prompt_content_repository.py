"""PostgreSQL projection of exact Prompt text and Task scalar parameters."""

from __future__ import annotations

from sqlalchemy import Text, cast, func, select

from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContent,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
)
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptTemplateRow,
    PromptVersionRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AITaskRow


class SqlAlchemyAIExecutionPromptTaskContentRepository:
    def load_exact(self, transaction: object, *,
                   grant: AITaskExecutionGrant) -> AIExecutionPromptTaskContent | None:
        if type(grant) is not AITaskExecutionGrant:
            return None
        grant.__post_init__()
        parameters_text = cast(AITaskRow.task_parameters, Text)
        row = _session(transaction).execute(select(
            AITaskRow.ai_task_id, AITaskRow.project_id, AITaskRow.job_ref,
            AITaskRow.requested_by, AITaskRow.trace_id, AITaskRow.task_type,
            AITaskRow.prompt_policy_ref, AITaskRow.prompt_policy_version,
            AITaskRow.prompt_template_ref, AITaskRow.prompt_version_no,
            AITaskRow.output_schema_ref, AITaskRow.context_policy_ref,
            AITaskRow.task_parameters, AITaskRow.task_parameters_fingerprint,
            PromptVersionRow.system_template, PromptVersionRow.user_template,
            PromptVersionRow.system_template_hash,
            PromptVersionRow.user_template_hash,
            PromptVersionRow.provider_policy_ref,
            PromptVersionRow.schema_version,
        ).join(
            PromptTemplateRow,
            PromptTemplateRow.prompt_template_id == AITaskRow.prompt_template_ref,
        ).join(
            PromptVersionRow,
            (PromptVersionRow.prompt_template_id
             == AITaskRow.prompt_template_ref)
            & (PromptVersionRow.version_no == AITaskRow.prompt_version_no),
        ).where(
            AITaskRow.ai_task_id == grant.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == grant.project_id,
            AITaskRow.job_ref == grant.job_id,
            AITaskRow.requested_by == grant.requested_by,
            AITaskRow.trace_id == grant.trace_id,
            AITaskRow.task_type == grant.task_type,
            AITaskRow.task_state == "QUEUED",
            AITaskRow.current_invocation_ref.is_(None),
            AITaskRow.started_at.is_(None),
            AITaskRow.prompt_policy_ref == grant.prompt_policy_ref,
            AITaskRow.prompt_policy_version == grant.prompt_policy_version,
            AITaskRow.prompt_template_ref == grant.prompt_template_id,
            AITaskRow.prompt_version_no == grant.prompt_version_no,
            AITaskRow.output_schema_ref == grant.output_schema_ref,
            AITaskRow.context_policy_ref == grant.context_policy_ref,
            AITaskRow.task_parameters.is_not(None),
            AITaskRow.task_parameters_fingerprint
            == grant.task_parameters_fingerprint,
            AITaskRow.task_parameters_fingerprint
            == func.sha256(func.convert_to(parameters_text, "UTF8")),
            PromptTemplateRow.task_type == grant.task_type,
            PromptTemplateRow.scope == "DEPLOYMENT",
            PromptTemplateRow.template_state == "ACTIVE",
            PromptTemplateRow.active_version_no == grant.prompt_version_no,
            PromptVersionRow.system_template_hash
            == grant.system_template_hash,
            PromptVersionRow.user_template_hash == grant.user_template_hash,
            PromptVersionRow.provider_policy_ref == grant.provider_policy_ref,
            PromptVersionRow.output_schema_ref == grant.output_schema_ref,
            PromptVersionRow.schema_version == grant.schema_version,
            PromptVersionRow.rag_policy_ref == grant.context_policy_ref,
        ).with_for_update(of=AITaskRow)
          .execution_options(autoflush=False)).one_or_none()
        if row is None or type(row.task_parameters) is not dict:
            return None
        return AIExecutionPromptTaskContent(
            row.ai_task_id, row.project_id, row.job_ref, row.requested_by,
            row.trace_id, row.task_type, row.prompt_policy_ref,
            row.prompt_policy_version, row.prompt_template_ref,
            row.prompt_version_no, row.system_template, row.user_template,
            row.system_template_hash, row.user_template_hash,
            row.provider_policy_ref, row.output_schema_ref,
            row.schema_version, row.context_policy_ref,
            dict(row.task_parameters), bytes(row.task_parameters_fingerprint),
        )
