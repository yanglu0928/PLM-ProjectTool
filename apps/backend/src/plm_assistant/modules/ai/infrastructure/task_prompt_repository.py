"""Locked PostgreSQL Prompt owner projection for AI Task submission."""

from __future__ import annotations

from sqlalchemy import Text, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB

from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskPromptSnapshot, ResolvedAITaskSubmissionPolicy,
)
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptTemplateRow, PromptVersionRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session


class SqlAlchemyAITaskPromptCurrentRepository:
    def resolve_current(self, transaction: object, *,
                        policy: ResolvedAITaskSubmissionPolicy) -> AITaskPromptSnapshot | None:
        if type(policy) is not ResolvedAITaskSubmissionPolicy:
            return None
        parameters = cast(literal(policy.task_parameters_json, type_=Text), JSONB)
        parameters_text = cast(parameters, Text)
        row = _session(transaction).execute(select(
            PromptTemplateRow.prompt_template_id,
            PromptTemplateRow.active_version_no,
            PromptVersionRow.output_schema_ref,
            PromptVersionRow.rag_policy_ref,
            parameters_text.label("task_parameters_json"),
            func.sha256(func.convert_to(parameters_text, "UTF8")).label("fingerprint"),
        ).join(
            PromptVersionRow,
            (PromptVersionRow.prompt_template_id == PromptTemplateRow.prompt_template_id)
            & (PromptVersionRow.version_no == PromptTemplateRow.active_version_no),
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
        return AITaskPromptSnapshot(
            row.prompt_template_id, row.active_version_no, policy.reference,
            policy.policy_version, policy.purpose_ref, row.output_schema_ref,
            row.rag_policy_ref, row.task_parameters_json, bytes(row.fingerprint),
        )
