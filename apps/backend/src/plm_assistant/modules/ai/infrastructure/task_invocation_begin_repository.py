"""PostgreSQL atomic begin for one AI Task Invocation attempt."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select

from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import AIInvocationRow, AITaskRow


class SqlAlchemyAITaskInvocationBeginRepository:
    def begin(self, transaction: object, *, grant: AITaskExecutionGrant,
              now: datetime) -> uuid.UUID:
        if (type(grant) is not AITaskExecutionGrant
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise RuntimeError("invalid AI Invocation begin")
        grant.__post_init__()
        now = now.astimezone(timezone.utc)
        if now >= grant.valid_until.astimezone(timezone.utc):
            raise RuntimeError("expired AI Invocation grant")
        session = _session(transaction)
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == grant.ai_task_id,
            AITaskRow.project_id == grant.project_id,
            AITaskRow.job_ref == grant.job_id,
        ).with_for_update().execution_options(autoflush=False))
        if (task is None or task.task_state != "QUEUED"
                or task.current_invocation_ref is not None
                or task.started_at is not None
                or task.content_plan_ref != grant.content_plan_id
                or task.input_fingerprint != grant.source_refs_fingerprint):
            raise RuntimeError("AI Task is not ready for Invocation")
        invocation_id = session.execute(insert(AIInvocationRow).values(
            ai_task_id=grant.ai_task_id,
            attempt_no=grant.attempt_no,
            scope="PROJECT",
            project_id=grant.project_id,
            ai_provider_id=grant.ai_provider_id,
            provider_config_version_id=grant.provider_config_version_id,
            ai_model_id=grant.ai_model_id,
            model_revision_observed=grant.model_revision,
            prompt_template_id=grant.prompt_template_id,
            prompt_version_no=grant.prompt_version_no,
            output_schema_ref=grant.output_schema_ref,
            schema_version=grant.schema_version,
            input_fingerprint=grant.source_refs_fingerprint,
            egress_authorization_mode="AUTHORIZED",
            egress_authorization_snapshot_id=grant.egress_snapshot_id,
            request_payload_ref=None,
            request_payload_fingerprint=grant.approved_payload_fingerprint,
            content_plan_ref=grant.content_plan_id,
            retrieval_run_ref=None,
            context_bundle_fingerprint=None,
            invocation_state="PENDING",
            schema_validation_required=True,
            schema_validation_state="PENDING",
            created_at=now,
        ).returning(AIInvocationRow.ai_invocation_id)).scalar_one()
        task.current_invocation_ref = invocation_id
        task.task_state = "RUNNING"
        task.started_at = now
        task.lock_version += 1
        session.flush()
        return invocation_id
