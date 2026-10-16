"""Minimal PostgreSQL AI Invocation history projection."""

from __future__ import annotations

import hmac
import uuid

from sqlalchemy import and_, or_, select

from plm_assistant.modules.ai.application.invocation_read import (
    AIInvocationCandidates,
    AIInvocationContextView,
    AIInvocationReadError,
    AIInvocationView,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIExecutionContentPlanRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow


class SqlAlchemyAIInvocationReadRepository:
    def list_page(
        self, transaction: object, *, project_id: uuid.UUID,
        ai_task_id: uuid.UUID, before: tuple[int, uuid.UUID] | None,
        limit: int,
    ) -> AIInvocationCandidates:
        if (any(type(value) is not uuid.UUID or not value.int
                for value in (project_id, ai_task_id))
                or type(limit) is not int or not 1 <= limit <= 100
                or before is not None and (
                    type(before) is not tuple or len(before) != 2
                    or type(before[0]) is not int or before[0] < 1
                    or type(before[1]) is not uuid.UUID or not before[1].int)):
            raise AIInvocationReadError()
        statement = select(
            AIInvocationRow.ai_invocation_id, AIInvocationRow.ai_task_id,
            AIInvocationRow.project_id, AIInvocationRow.attempt_no,
            AIInvocationRow.ai_provider_id,
            AIInvocationRow.provider_config_version_id,
            AIInvocationRow.ai_model_id,
            AIInvocationRow.model_revision_observed,
            AIInvocationRow.prompt_template_id,
            AIInvocationRow.prompt_version_no,
            AIInvocationRow.output_schema_ref,
            AIInvocationRow.schema_version,
            AIInvocationRow.content_plan_ref,
            AIInvocationRow.retrieval_run_ref,
            AIInvocationRow.context_bundle_fingerprint,
            AIInvocationRow.invocation_state,
            AIInvocationRow.schema_validation_state,
            AIInvocationRow.usage_input_tokens,
            AIInvocationRow.usage_output_tokens,
            AIInvocationRow.latency_ms,
            AIInvocationRow.error_code,
            AIInvocationRow.retryable,
            AIInvocationRow.created_at,
            AIInvocationRow.started_at,
            AIInvocationRow.completed_at,
            AIExecutionContentPlanRow.content_plan_id,
            AIExecutionContentPlanRow.content_plan_version,
            AIExecutionContentPlanRow.project_id.label("content_plan_project_id"),
            AIExecutionContentPlanRow.context_policy_ref,
            AIExecutionContentPlanRow.context_mode,
            AIExecutionContentPlanRow.retrieval_run_id,
            AIExecutionContentPlanRow.context_bundle_id,
            AIExecutionContentPlanRow.context_bundle_fingerprint.label(
                "plan_context_bundle_fingerprint",
            ),
        ).select_from(AIInvocationRow).outerjoin(
            AIExecutionContentPlanRow,
            AIInvocationRow.content_plan_ref
            == AIExecutionContentPlanRow.content_plan_id,
        ).where(
            AIInvocationRow.scope == "PROJECT",
            AIInvocationRow.project_id == project_id,
            AIInvocationRow.ai_task_id == ai_task_id,
        )
        if before is not None:
            statement = statement.where(or_(
                AIInvocationRow.attempt_no < before[0],
                and_(AIInvocationRow.attempt_no == before[0],
                     AIInvocationRow.ai_invocation_id < before[1]),
            ))
        rows = _session(transaction).execute(
            statement.order_by(
                AIInvocationRow.attempt_no.desc(),
                AIInvocationRow.ai_invocation_id.desc(),
            ).limit(limit + 1).execution_options(autoflush=False)
        ).all()
        has_more = len(rows) > limit
        views: list[AIInvocationView] = []
        for row in rows[:limit]:
            if row.content_plan_ref is None:
                if any(value is not None for value in (
                    row.retrieval_run_ref, row.context_bundle_fingerprint,
                    row.content_plan_id, row.content_plan_version,
                    row.content_plan_project_id, row.context_policy_ref,
                    row.context_mode, row.retrieval_run_id,
                    row.context_bundle_id, row.plan_context_bundle_fingerprint,
                )):
                    raise AIInvocationReadError()
                context = None
            else:
                if (row.content_plan_id != row.content_plan_ref
                        or row.content_plan_project_id != project_id
                        or row.retrieval_run_ref != row.retrieval_run_id
                        or ((row.context_bundle_fingerprint is None)
                            != (row.plan_context_bundle_fingerprint is None))
                        or row.context_bundle_fingerprint is not None and not hmac.compare_digest(
                            row.context_bundle_fingerprint,
                            row.plan_context_bundle_fingerprint)):
                    raise AIInvocationReadError()
                context = AIInvocationContextView(
                    row.content_plan_id, row.content_plan_version,
                    row.context_policy_ref, row.context_mode,
                    row.retrieval_run_id, row.context_bundle_id,
                )
            views.append(AIInvocationView(
                row.ai_invocation_id, row.ai_task_id, row.project_id,
                row.attempt_no, row.ai_provider_id,
                row.provider_config_version_id, row.ai_model_id,
                row.model_revision_observed, row.prompt_template_id,
                row.prompt_version_no, row.output_schema_ref,
                row.schema_version, context, row.invocation_state,
                row.schema_validation_state, row.usage_input_tokens,
                row.usage_output_tokens, row.latency_ms, row.error_code,
                row.retryable, row.created_at, row.started_at,
                row.completed_at,
            ))
        return AIInvocationCandidates(tuple(views), has_more)
