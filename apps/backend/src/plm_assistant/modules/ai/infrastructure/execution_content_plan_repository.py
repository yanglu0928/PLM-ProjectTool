"""PostgreSQL persistence for immutable, no-content AI execution plans."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, text

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    PersistedAIExecutionContentPlan,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIExecutionContentPlanRow,
    AIExecutionContentSourceRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session


class SqlAlchemyAIExecutionContentPlanRepository:
    def get_by_id(
        self, transaction: object, *, content_plan_id: uuid.UUID,
    ) -> PersistedAIExecutionContentPlan | None:
        if type(content_plan_id) is not uuid.UUID or not content_plan_id.int:
            return None
        return self._get(
            transaction,
            AIExecutionContentPlanRow.content_plan_id == content_plan_id,
        )

    def get_by_preview(
        self, transaction: object, *, egress_preview_id: uuid.UUID,
    ) -> PersistedAIExecutionContentPlan | None:
        if type(egress_preview_id) is not uuid.UUID or not egress_preview_id.int:
            return None
        return self._get(
            transaction,
            AIExecutionContentPlanRow.egress_preview_id == egress_preview_id,
        )

    def add(
        self, transaction: object, *, value: PersistedAIExecutionContentPlan,
    ) -> None:
        if type(value) is not PersistedAIExecutionContentPlan:
            raise ValueError("invalid AI execution Content Plan persistence value")
        value.__post_init__()
        session = _session(transaction)
        plan = value.plan
        prompt = plan.prompt
        context = plan.context
        session.execute(insert(AIExecutionContentPlanRow).values(
            content_plan_id=plan.content_plan_id,
            egress_preview_id=value.egress_preview_id,
            content_plan_version=plan.content_plan_version,
            project_id=plan.project_id,
            purpose_ref=plan.purpose_ref,
            task_type=plan.task_type,
            source_refs_fingerprint=plan.source_refs_fingerprint,
            prompt_policy_ref=prompt.prompt_policy_ref,
            prompt_policy_version=prompt.prompt_policy_version,
            prompt_template_id=prompt.prompt_template_id,
            prompt_version_no=prompt.prompt_version_no,
            system_template_hash=prompt.system_template_hash,
            user_template_hash=prompt.user_template_hash,
            provider_policy_ref=prompt.provider_policy_ref,
            output_schema_ref=prompt.output_schema_ref,
            schema_version=prompt.schema_version,
            rendering_policy_ref=prompt.rendering_policy_ref,
            rendering_policy_version=prompt.rendering_policy_version,
            task_parameters_fingerprint=plan.task_parameters_fingerprint,
            context_policy_ref=context.context_policy_ref,
            context_mode=context.mode,
            retrieval_run_id=context.retrieval_run_id,
            context_bundle_id=context.context_bundle_id,
            context_bundle_fingerprint=context.context_bundle_fingerprint,
            context_record_count=context.record_count,
            context_content_size_bytes=context.content_size_bytes,
            ai_provider_id=plan.ai_provider_id,
            provider_config_version_id=plan.provider_config_version_id,
            ai_model_id=plan.ai_model_id,
            provider_model_key=plan.provider_model_key,
            model_revision=plan.model_revision,
            data_region=plan.data_region,
            allowed_data_categories=list(plan.allowed_data_categories),
            minimal_payload_policy_ref=plan.minimal_payload_policy_ref,
            envelope_encoding_ref=plan.envelope_encoding_ref,
            envelope_encoding_version=plan.envelope_encoding_version,
            token_estimator_ref=plan.token_estimator_ref,
            token_estimator_version=plan.token_estimator_version,
            content_plan_fingerprint=value.plan_fingerprint,
            payload_fingerprint=value.payload_fingerprint,
            record_count=value.record_count,
            payload_bytes=value.payload_bytes,
            input_tokens=value.input_tokens,
        ))
        for source in plan.sources:
            session.execute(insert(AIExecutionContentSourceRow).values(
                content_plan_id=plan.content_plan_id,
                source_ordinal=source.ordinal,
                resource_type=source.resource_type,
                owner_module=source.owner_module,
                object_type=source.object_type,
                object_id=source.object_id,
                version_id=source.version_id,
                project_id=source.project_id,
                content_kind=source.content_kind,
                content_revision_id=source.content_revision_id,
                content_object_id=source.content_object_id,
                producer_ref=source.producer_ref,
                producer_version=source.producer_version,
                content_schema_ref=source.content_schema_ref,
                selection_policy_ref=source.selection_policy_ref,
                source_fingerprint=source.source_fingerprint,
                content_fingerprint=source.content_fingerprint,
                projection_fingerprint=source.projection_fingerprint,
                content_size_bytes=source.content_size_bytes,
                record_count=source.record_count,
            ))
        session.flush()
        session.execute(text(
            "SET CONSTRAINTS plm.trg_ai_content_plan_completeness, "
            "plm.trg_ai_content_source_completeness IMMEDIATE"
        ))
        session.execute(text(
            "SET CONSTRAINTS plm.trg_ai_content_plan_completeness, "
            "plm.trg_ai_content_source_completeness DEFERRED"
        ))

    def _get(self, transaction: object, condition: object) -> PersistedAIExecutionContentPlan | None:
        session = _session(transaction)
        root = session.execute(
            select(AIExecutionContentPlanRow).where(condition)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()
        if root is None:
            return None
        rows = session.execute(
            select(AIExecutionContentSourceRow).where(
                AIExecutionContentSourceRow.content_plan_id == root.content_plan_id,
            ).order_by(AIExecutionContentSourceRow.source_ordinal)
            .execution_options(autoflush=False)
        ).scalars().all()
        try:
            sources = tuple(AIExecutionContentSourceIdentity(
                row.source_ordinal, row.resource_type, row.owner_module,
                row.object_type, row.object_id, row.version_id, row.project_id,
                row.content_kind, row.content_revision_id, row.content_object_id,
                row.producer_ref, row.producer_version, row.content_schema_ref,
                row.selection_policy_ref, bytes(row.source_fingerprint),
                bytes(row.content_fingerprint), bytes(row.projection_fingerprint),
                row.content_size_bytes, row.record_count,
            ) for row in rows)
            prompt = AIExecutionPromptIdentity(
                root.prompt_policy_ref, root.prompt_policy_version,
                root.prompt_template_id, root.prompt_version_no,
                root.system_template_hash, root.user_template_hash,
                root.provider_policy_ref, root.output_schema_ref,
                root.schema_version, root.rendering_policy_ref,
                root.rendering_policy_version,
            )
            context = AIExecutionContextIdentity(
                root.context_policy_ref, root.context_mode,
                root.retrieval_run_id, root.context_bundle_id,
                (bytes(root.context_bundle_fingerprint)
                 if root.context_bundle_fingerprint is not None else None),
                root.context_record_count, root.context_content_size_bytes,
            )
            plan = AIExecutionContentPlan(
                root.content_plan_id, root.content_plan_version,
                root.project_id, root.purpose_ref, root.task_type,
                bytes(root.source_refs_fingerprint), sources, prompt,
                bytes(root.task_parameters_fingerprint), context,
                root.ai_provider_id, root.provider_config_version_id,
                root.ai_model_id, root.provider_model_key, root.model_revision,
                root.data_region, tuple(root.allowed_data_categories),
                root.minimal_payload_policy_ref, root.envelope_encoding_ref,
                root.envelope_encoding_version, root.token_estimator_ref,
                root.token_estimator_version,
            )
            return PersistedAIExecutionContentPlan(
                root.egress_preview_id, plan,
                bytes(root.content_plan_fingerprint),
                bytes(root.payload_fingerprint), root.record_count,
                root.payload_bytes, root.input_tokens,
            )
        except Exception:
            raise RuntimeError("invalid AI execution Content Plan history") from None
