"""PostgreSQL atomic SuggestionPayload, Invocation and Task success write."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select, text

from plm_assistant.modules.ai.application.provider_response_parser import (
    ParsedAISuggestion,
)
from plm_assistant.modules.ai.application.publish_suggestion_success import (
    AISuggestionEvidence,
    PublishedAITaskSuggestion,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    BegunAITaskInvocation,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    PreparedAITaskInvocation,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIInvocationRow,
    AISuggestionEvidenceRefRow,
    AISuggestionPayloadRow,
    AITaskRow,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class SqlAlchemyAITaskSuggestionSuccessRepository:
    def publish(
        self, transaction: object, *, parsed: ParsedAISuggestion,
        prepared: PreparedAITaskInvocation, begun: BegunAITaskInvocation,
        evidence: tuple[AISuggestionEvidence, ...],
    ) -> PublishedAITaskSuggestion:
        session = _session(transaction)
        grant = prepared.grant
        task = session.scalar(select(AITaskRow).where(
            AITaskRow.ai_task_id == grant.ai_task_id,
            AITaskRow.scope == "PROJECT",
            AITaskRow.project_id == grant.project_id,
            AITaskRow.job_ref == grant.job_id,
            AITaskRow.requested_by == grant.requested_by,
            AITaskRow.trace_id == grant.trace_id,
            AITaskRow.content_plan_ref == grant.content_plan_id,
            AITaskRow.output_schema_ref == grant.output_schema_ref,
            AITaskRow.task_state == "RUNNING",
            AITaskRow.suggestion_state == "NONE",
            AITaskRow.current_invocation_ref == begun.ai_invocation_id,
            AITaskRow.completed_at.is_(None),
            AITaskRow.error_code.is_(None),
            AITaskRow.retryable.is_(None),
        ).with_for_update().execution_options(autoflush=False))
        invocation = session.scalar(select(AIInvocationRow).where(
            AIInvocationRow.ai_invocation_id == begun.ai_invocation_id,
            AIInvocationRow.ai_task_id == grant.ai_task_id,
            AIInvocationRow.attempt_no == grant.attempt_no,
            AIInvocationRow.scope == "PROJECT",
            AIInvocationRow.project_id == grant.project_id,
            AIInvocationRow.output_schema_ref == parsed.output_schema_ref,
            AIInvocationRow.schema_version == parsed.schema_version,
            AIInvocationRow.content_plan_ref == grant.content_plan_id,
            AIInvocationRow.invocation_state == "RUNNING",
            AIInvocationRow.started_at.is_not(None),
            AIInvocationRow.completed_at.is_(None),
            AIInvocationRow.schema_validation_required.is_(True),
            AIInvocationRow.schema_validation_state == "PENDING",
            AIInvocationRow.suggestion_payload_ref.is_(None),
            AIInvocationRow.response_fingerprint.is_(None),
            AIInvocationRow.error_code.is_(None),
            AIInvocationRow.retryable.is_(None),
        ).with_for_update().execution_options(autoflush=False))
        if task is None or invocation is None or not evidence:
            raise RuntimeError("AI Task suggestion publication state mismatch")
        try:
            canonical = json.loads(parsed.canonical_payload_json)
        except (json.JSONDecodeError, UnicodeError):
            raise RuntimeError("invalid canonical AI suggestion") from None
        completed_at = session.scalar(select(func.clock_timestamp()))
        suggestion_id = uuid.UUID(new_uuid7())
        session.add(AISuggestionPayloadRow(
            suggestion_payload_id=suggestion_id,
            ai_invocation_id=begun.ai_invocation_id,
            ai_task_id=grant.ai_task_id,
            scope="PROJECT", project_id=grant.project_id,
            output_schema_ref=parsed.output_schema_ref,
            schema_version=parsed.schema_version,
            canonical_payload=canonical,
            payload_fingerprint=parsed.payload_fingerprint,
            fact_status="NOT_FORMAL_FACT", quality_flags=[],
            created_at=completed_at,
        ))
        session.flush()
        for item in evidence:
            session.add(AISuggestionEvidenceRefRow(
                suggestion_payload_id=suggestion_id,
                ref_ordinal=item.ordinal,
                scope="PROJECT", project_id=grant.project_id,
                owner_module=item.owner_module,
                object_type=item.object_type,
                object_id=item.object_id,
                version_id=item.version_id,
                content_fingerprint=item.content_fingerprint,
                created_at=completed_at,
            ))
        session.flush()
        invocation.suggestion_payload_ref = suggestion_id
        invocation.response_fingerprint = parsed.response_fingerprint
        invocation.usage_input_tokens = parsed.usage_input_tokens
        invocation.usage_output_tokens = parsed.usage_output_tokens
        invocation.latency_ms = parsed.latency_ms
        invocation.schema_validation_state = "VALID"
        invocation.invocation_state = "SUCCEEDED"
        invocation.completed_at = completed_at
        invocation.lock_version += 1
        task.task_state = "SUCCEEDED"
        task.suggestion_state = "AVAILABLE"
        task.completed_at = completed_at
        task.lock_version += 1
        session.flush()
        session.execute(text(
            "SET CONSTRAINTS plm.fk_ai_invocations__suggestion_payload IMMEDIATE"
        ))
        session.execute(text(
            "SET CONSTRAINTS plm.fk_ai_invocations__suggestion_payload DEFERRED"
        ))
        return PublishedAITaskSuggestion(suggestion_id, completed_at)
