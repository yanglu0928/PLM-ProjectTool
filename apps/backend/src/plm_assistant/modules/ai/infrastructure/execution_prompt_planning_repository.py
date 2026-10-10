"""Locked active Prompt and parameter projection for Egress Preview planning."""

from __future__ import annotations

import json

from sqlalchemy import Text, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB

from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptPlanningContent,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    ResolvedAITaskSubmissionPolicy,
)
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptTemplateRow,
    PromptVersionRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session


class SqlAlchemyAIExecutionPromptPlanningRepository:
    def load_current(
        self, transaction: object, *, policy: ResolvedAITaskSubmissionPolicy,
    ) -> AIExecutionPromptPlanningContent | None:
        if type(policy) is not ResolvedAITaskSubmissionPolicy:
            return None
        parameters = cast(literal(policy.task_parameters_json, type_=Text), JSONB)
        parameters_text = cast(parameters, Text)
        row = _session(transaction).execute(select(
            PromptTemplateRow.task_type,
            PromptTemplateRow.prompt_template_id,
            PromptTemplateRow.active_version_no,
            PromptVersionRow.system_template,
            PromptVersionRow.user_template,
            PromptVersionRow.system_template_hash,
            PromptVersionRow.user_template_hash,
            PromptVersionRow.provider_policy_ref,
            PromptVersionRow.output_schema_ref,
            PromptVersionRow.schema_version,
            PromptVersionRow.rag_policy_ref,
            parameters_text.label("task_parameters_json"),
            func.sha256(func.convert_to(parameters_text, "UTF8")).label(
                "task_parameters_fingerprint"
            ),
        ).join(
            PromptVersionRow,
            (PromptVersionRow.prompt_template_id
             == PromptTemplateRow.prompt_template_id)
            & (PromptVersionRow.version_no
               == PromptTemplateRow.active_version_no),
        ).where(
            PromptTemplateRow.prompt_template_id == policy.prompt_template_id,
            PromptTemplateRow.scope == "DEPLOYMENT",
            PromptTemplateRow.template_state == "ACTIVE",
            PromptTemplateRow.task_type == policy.task_type,
            PromptVersionRow.output_schema_ref == policy.output_schema_ref,
            PromptVersionRow.rag_policy_ref == policy.context_policy_ref,
        ).with_for_update(of=PromptTemplateRow, key_share=True)
          .execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None
        try:
            task_parameters = json.loads(row.task_parameters_json)
        except (TypeError, ValueError):
            return None
        if type(task_parameters) is not dict:
            return None
        return AIExecutionPromptPlanningContent(
            row.task_type, policy.reference, policy.policy_version,
            row.prompt_template_id, row.active_version_no,
            row.system_template, row.user_template,
            row.system_template_hash, row.user_template_hash,
            row.provider_policy_ref, row.output_schema_ref,
            row.schema_version, row.rag_policy_ref, task_parameters,
            bytes(row.task_parameters_fingerprint),
        )
