"""PostgreSQL atomic AI Task, Job, Outbox, input, and egress snapshot persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import Text, cast, insert, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.application.create_task import (
    AITaskPersistenceRequest, CreatedAITask,
)
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow, AITaskInputRefRow, AITaskRow,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow
from plm_assistant.modules.platform.application.trace_context import new_uuid7


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError):
        raise RuntimeError("active AI Task transaction required") from None
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active AI Task transaction required")
    return session


class SqlAlchemyAITaskCreateRepository:
    def create(self, transaction: object, *, request: AITaskPersistenceRequest) -> CreatedAITask:
        if type(request) is not AITaskPersistenceRequest:
            raise ValueError("invalid AI Task persistence request")
        session = _session(transaction)
        task_id, job_id, event_id, snapshot_id = (
            uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7()),
            uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7()),
        )
        payload = {
            "ai_task_id": str(task_id),
            "egress_authorization_ref": str(request.egress.authorization_ref),
            "input_fingerprint": request.input_fingerprint.hex(),
        }
        session.execute(insert(JobRow).values(
            job_id=job_id, owner_module="ai", job_type="AI_TASK_EXECUTE",
            scope="PROJECT", project_id=request.project_id, actor_ref=request.requested_by,
            trace_id=str(request.trace_id), payload_refs=payload,
            idempotency_key=str(task_id), max_attempts=request.egress.max_retry_attempts,
        ))
        session.execute(insert(AITaskRow).values(
            ai_task_id=task_id, scope="PROJECT", project_id=request.project_id,
            task_type=request.task_type, requested_by=request.requested_by,
            input_fingerprint=request.input_fingerprint,
            prompt_policy_ref=request.prompt.policy_ref,
            output_schema_ref=request.prompt.output_schema_ref,
            context_policy_ref=request.prompt.context_policy_ref,
            prompt_template_ref=request.prompt.prompt_template_ref,
            prompt_version_no=request.prompt.prompt_version_no,
            task_parameters=cast(
                literal(request.prompt.task_parameters_json, type_=Text), JSONB,
            ),
            task_parameters_fingerprint=request.prompt.task_parameters_fingerprint,
            job_ref=job_id, trace_id=request.trace_id,
        ))
        for ordinal, item in enumerate(request.inputs, 1):
            session.execute(insert(AITaskInputRefRow).values(
                ai_task_id=task_id, ref_ordinal=ordinal, scope=item.scope,
                project_id=item.project_id, owner_module=item.owner_module,
                object_type=item.object_type, object_id=item.object_id,
                version_id=item.version_id,
            ))
        egress = request.egress
        session.execute(insert(AIEgressAuthorizationSnapshotRow).values(
            egress_authorization_snapshot_id=snapshot_id, ai_task_id=task_id,
            scope="PROJECT", project_id=request.project_id,
            authorization_ref=egress.authorization_ref, purpose_ref=egress.purpose_ref,
            ai_provider_id=egress.ai_provider_id,
            provider_config_version_id=egress.provider_config_version_id,
            ai_model_id=egress.ai_model_id, data_region=egress.data_region,
            allowed_data_categories=list(egress.allowed_data_categories),
            authorization_fingerprint=egress.authorization_fingerprint,
            preview_payload_fingerprint=egress.preview_payload_fingerprint,
            source_refs_fingerprint=egress.source_refs_fingerprint,
            approved_by=egress.approved_by, approved_role=egress.approved_role,
            approved_at=egress.approved_at, valid_until=egress.valid_until,
            max_payload_bytes=egress.max_payload_bytes,
            max_input_tokens=egress.max_input_tokens,
            max_retry_attempts=egress.max_retry_attempts,
            authorization_state_at_capture=egress.authorization_state,
        ))
        session.execute(insert(OutboxEventRow).values(
            event_id=event_id, event_type="AI_TASK_QUEUED", owner_module="ai",
            scope="PROJECT", project_id=request.project_id, aggregate_ref=task_id,
            aggregate_version=0, payload_refs={"ai_task_id": str(task_id),
                                               "job_id": str(job_id)},
            idempotency_key=str(task_id), trace_id=str(request.trace_id), max_attempts=5,
        ))
        session.flush()
        return CreatedAITask(task_id, job_id)

    def replay(self, transaction: object, *, ai_task_id: uuid.UUID,
               project_id: uuid.UUID, requested_by: uuid.UUID) -> CreatedAITask | None:
        if any(type(value) is not uuid.UUID or not value.int for value in (
            ai_task_id, project_id, requested_by,
        )):
            return None
        session = _session(transaction)
        row = session.execute(
            select(AITaskRow.ai_task_id, AITaskRow.job_ref).where(
                AITaskRow.ai_task_id == ai_task_id,
                AITaskRow.scope == "PROJECT", AITaskRow.project_id == project_id,
                AITaskRow.requested_by == requested_by,
                AITaskRow.job_ref.is_not(None),
            ).execution_options(autoflush=False)
        ).one_or_none()
        if row is None or type(row.job_ref) is not uuid.UUID or not row.job_ref.int:
            return None
        job = session.execute(select(JobRow).where(
            JobRow.job_id == row.job_ref, JobRow.owner_module == "ai",
            JobRow.job_type == "AI_TASK_EXECUTE", JobRow.scope == "PROJECT",
            JobRow.project_id == project_id, JobRow.actor_ref == requested_by,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if (job is None or type(job.payload_refs) is not dict
                or job.payload_refs.get("ai_task_id") != str(ai_task_id)):
            return None
        return CreatedAITask(ai_task_id, row.job_ref)
