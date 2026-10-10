"""PostgreSQL persistence for immutable explicit AI Task retry generations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select

from plm_assistant.modules.ai.application.request_task_retry import (
    AITaskRetryBinding,
    AITaskRetryEgressProof,
    AITaskRetryError,
    AITaskRetryGeneration,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow,
    AITaskInputRefRow,
    AITaskRetryGenerationRow,
    AITaskRow,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow
from plm_assistant.modules.platform.application.trace_context import new_uuid7


@dataclass(frozen=True, slots=True)
class PendingAITaskRetryGeneration:
    source_ai_task_id: uuid.UUID
    source_job_id: uuid.UUID
    new_ai_task_id: uuid.UUID
    new_job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    root_ai_task_id: uuid.UUID
    generation_no: int
    expected_source_version: int


class SqlAlchemyAITaskRetryRepository:
    def binding(self, transaction: object, *, job_id: uuid.UUID,
                project_id: uuid.UUID) -> AITaskRetryBinding | None:
        session = _session(transaction)
        row = session.execute(
            select(AITaskRow, JobRow, AIEgressAuthorizationSnapshotRow).join(
                JobRow, JobRow.job_id == AITaskRow.job_ref,
            ).join(
                AIEgressAuthorizationSnapshotRow,
                AIEgressAuthorizationSnapshotRow.ai_task_id == AITaskRow.ai_task_id,
            ).where(
                JobRow.job_id == job_id, JobRow.owner_module == "ai",
                JobRow.job_type == "AI_TASK_EXECUTE", JobRow.scope == "PROJECT",
                JobRow.project_id == project_id,
                AITaskRow.scope == "PROJECT", AITaskRow.project_id == project_id,
            ).with_for_update(of=(AITaskRow, JobRow, AIEgressAuthorizationSnapshotRow))
        ).one_or_none()
        if row is None:
            return None
        task, job, snap = row
        if (task.job_ref != job.job_id or task.task_state != job.state
                or task.task_state not in {"FAILED", "CANCELLED"}
                or task.suggestion_state != "NONE" or task.completed_at is None
                or (task.task_state == "FAILED" and task.retryable is not True)
                or type(task.requested_by) is not uuid.UUID):
            raise AITaskRetryError("JOB_NOT_RETRYABLE")
        try:
            proof = AITaskRetryEgressProof(
                snap.authorization_ref, snap.purpose_ref, snap.ai_provider_id,
                snap.provider_config_version_id, snap.ai_model_id,
                snap.data_region, tuple(snap.allowed_data_categories),
                snap.authorization_fingerprint, snap.preview_payload_fingerprint,
                snap.source_refs_fingerprint, snap.approved_by,
                snap.approved_role, snap.approved_at, snap.valid_until,
                snap.content_plan_ref, snap.max_payload_bytes,
                snap.max_input_tokens, snap.max_retry_attempts,
                snap.authorization_state_at_capture,
            )
        except (TypeError, AttributeError):
            raise AITaskRetryError("JOB_NOT_RETRYABLE") from None
        return AITaskRetryBinding(
            task.ai_task_id, job.job_id, project_id, task.requested_by,
            task.task_type, task.task_state, task.retryable,
            task.input_fingerprint, task.lock_version, job.lock_version, proof,
        )

    def create(self, transaction: object, *, binding: AITaskRetryBinding,
               requested_by: uuid.UUID, trace_id: uuid.UUID,
               expected_source_version: int) -> PendingAITaskRetryGeneration:
        session = _session(transaction)
        child = session.execute(select(AITaskRetryGenerationRow.new_ai_task_id).where(
            AITaskRetryGenerationRow.source_ai_task_id == binding.ai_task_id,
        )).scalar_one_or_none()
        if child is not None:
            raise AITaskRetryError("JOB_NOT_RETRYABLE")
        prior = session.execute(select(AITaskRetryGenerationRow).where(
            AITaskRetryGenerationRow.new_ai_task_id == binding.ai_task_id,
        )).scalar_one_or_none()
        root_id = binding.ai_task_id if prior is None else prior.root_ai_task_id
        generation_no = 1 if prior is None else prior.generation_no + 1
        if generation_no > binding.egress.max_retry_attempts:
            raise AITaskRetryError("JOB_NOT_RETRYABLE")
        source = session.get(AITaskRow, binding.ai_task_id)
        source_job = session.get(JobRow, binding.job_id)
        snapshot = session.execute(select(AIEgressAuthorizationSnapshotRow).where(
            AIEgressAuthorizationSnapshotRow.ai_task_id == binding.ai_task_id,
        )).scalar_one()
        task_id, job_id, event_id, snapshot_id = (
            uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7()),
            uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7()),
        )
        session.execute(insert(JobRow).values(
            job_id=job_id, owner_module="ai", job_type="AI_TASK_EXECUTE",
            scope="PROJECT", project_id=binding.project_id,
            actor_ref=requested_by, trace_id=str(trace_id),
            payload_refs={
                "ai_task_id": str(task_id),
                "egress_authorization_ref": str(binding.egress.authorization_ref),
                "input_fingerprint": binding.input_fingerprint.hex(),
            }, idempotency_key=str(task_id), max_attempts=source_job.max_attempts,
        ))
        session.execute(insert(AITaskRow).values(
            ai_task_id=task_id, scope=source.scope, project_id=source.project_id,
            task_type=source.task_type, requested_by=requested_by,
            input_fingerprint=source.input_fingerprint,
            prompt_policy_ref=source.prompt_policy_ref,
            output_schema_ref=source.output_schema_ref,
            context_policy_ref=source.context_policy_ref,
            prompt_template_ref=source.prompt_template_ref,
            prompt_version_no=source.prompt_version_no,
            prompt_policy_version=source.prompt_policy_version,
            task_parameters=source.task_parameters,
            task_parameters_fingerprint=source.task_parameters_fingerprint,
            content_plan_ref=source.content_plan_ref,
            job_ref=job_id, trace_id=trace_id,
        ))
        inputs = session.execute(select(AITaskInputRefRow).where(
            AITaskInputRefRow.ai_task_id == binding.ai_task_id,
        ).order_by(AITaskInputRefRow.ref_ordinal)).scalars().all()
        for item in inputs:
            session.execute(insert(AITaskInputRefRow).values(
                ai_task_id=task_id, ref_ordinal=item.ref_ordinal,
                scope=item.scope, project_id=item.project_id,
                owner_module=item.owner_module, object_type=item.object_type,
                object_id=item.object_id, version_id=item.version_id,
            ))
        session.execute(insert(AIEgressAuthorizationSnapshotRow).values(
            egress_authorization_snapshot_id=snapshot_id, ai_task_id=task_id,
            scope=snapshot.scope, project_id=snapshot.project_id,
            authorization_ref=snapshot.authorization_ref,
            purpose_ref=snapshot.purpose_ref, ai_provider_id=snapshot.ai_provider_id,
            provider_config_version_id=snapshot.provider_config_version_id,
            ai_model_id=snapshot.ai_model_id, data_region=snapshot.data_region,
            allowed_data_categories=snapshot.allowed_data_categories,
            authorization_fingerprint=snapshot.authorization_fingerprint,
            preview_payload_fingerprint=snapshot.preview_payload_fingerprint,
            source_refs_fingerprint=snapshot.source_refs_fingerprint,
            approved_by=snapshot.approved_by, approved_role=snapshot.approved_role,
            approved_at=snapshot.approved_at, valid_until=snapshot.valid_until,
            max_payload_bytes=snapshot.max_payload_bytes,
            max_input_tokens=snapshot.max_input_tokens,
            max_retry_attempts=snapshot.max_retry_attempts,
            authorization_state_at_capture=snapshot.authorization_state_at_capture,
            content_plan_ref=snapshot.content_plan_ref,
        ))
        session.execute(insert(OutboxEventRow).values(
            event_id=event_id, event_type="AI_TASK_QUEUED", owner_module="ai",
            scope="PROJECT", project_id=binding.project_id,
            aggregate_ref=task_id, aggregate_version=0,
            payload_refs={"ai_task_id": str(task_id), "job_id": str(job_id)},
            idempotency_key=str(task_id), trace_id=str(trace_id), max_attempts=5,
        ))
        session.flush()
        return PendingAITaskRetryGeneration(
            binding.ai_task_id, binding.job_id, task_id, job_id,
            binding.project_id, requested_by, root_id, generation_no,
            expected_source_version,
        )

    def record_lineage(self, transaction: object, *,
                       draft: PendingAITaskRetryGeneration,
                       retry_audit_event_id: uuid.UUID) -> AITaskRetryGeneration:
        session = _session(transaction)
        row = session.execute(insert(AITaskRetryGenerationRow).values(
            new_ai_task_id=draft.new_ai_task_id,
            source_ai_task_id=draft.source_ai_task_id,
            root_ai_task_id=draft.root_ai_task_id,
            source_job_id=draft.source_job_id, new_job_id=draft.new_job_id,
            requested_by=draft.requested_by,
            retry_audit_event_id=retry_audit_event_id,
            generation_no=draft.generation_no,
            expected_source_version=draft.expected_source_version,
            first_job_version=0,
        ).returning(AITaskRetryGenerationRow)).scalar_one()
        return self._generation(session, row)

    def replay(self, transaction: object, *, new_ai_task_id: uuid.UUID,
               source_job_id: uuid.UUID, project_id: uuid.UUID,
               requested_by: uuid.UUID) -> AITaskRetryGeneration | None:
        session = _session(transaction)
        row = session.execute(
            select(AITaskRetryGenerationRow).join(
                AITaskRow,
                AITaskRow.ai_task_id == AITaskRetryGenerationRow.new_ai_task_id,
            ).where(
                AITaskRetryGenerationRow.new_ai_task_id == new_ai_task_id,
                AITaskRetryGenerationRow.source_job_id == source_job_id,
                AITaskRetryGenerationRow.requested_by == requested_by,
                AITaskRow.project_id == project_id,
            )
        ).scalar_one_or_none()
        return None if row is None else self._generation(session, row)

    @staticmethod
    def _generation(session, row: AITaskRetryGenerationRow) -> AITaskRetryGeneration:
        # Project scope remains owned by Task; lineage does not duplicate it.
        project_id = session.execute(select(AITaskRow.project_id).where(
            AITaskRow.ai_task_id == row.new_ai_task_id,
        )).scalar_one()
        return AITaskRetryGeneration(
            row.source_ai_task_id, row.source_job_id, row.new_ai_task_id,
            row.new_job_id, project_id, row.requested_by,
            row.root_ai_task_id, row.generation_no,
            row.expected_source_version, row.retry_audit_event_id,
            row.created_at,
        )
