"""AIModel safe transition and immutable first-result storage."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update

from plm_assistant.modules.ai.application.change_model_state import (
    AIModelStateError, AIModelStateResult,
)
from plm_assistant.modules.ai.infrastructure.model_create_repository import _session
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow, AIModelStateResultRow
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow


class SqlAlchemyAIModelStateRepository:
    def locked_state(self, transaction: object, *, model_id: uuid.UUID) -> tuple[str, int] | None:
        if type(model_id) is not uuid.UUID or model_id.int == 0:
            raise AIModelStateError("VALIDATION_FAILED")
        row = _session(transaction).execute(
            select(AIModelRow.model_state, AIModelRow.lock_version)
            .where(AIModelRow.ai_model_id == model_id)
            .with_for_update(of=AIModelRow)
            .execution_options(autoflush=False)
        ).one_or_none()
        if row is None:
            return None
        if (row.model_state not in {"AVAILABLE", "SUSPENDED", "RETIRED"}
                or type(row.lock_version) is not int or row.lock_version < 0):
            raise AIModelStateError()
        return row.model_state, row.lock_version

    def change(self, transaction: object, *, model_id: uuid.UUID, before_state: str,
               state: str, expected_lock_version: int) -> int:
        if (type(model_id) is not uuid.UUID or model_id.int == 0
                or (before_state, state) not in {
                    ("AVAILABLE", "SUSPENDED"), ("AVAILABLE", "RETIRED"),
                    ("SUSPENDED", "RETIRED")}
                or type(expected_lock_version) is not int
                or not 0 <= expected_lock_version <= 9223372036854775806):
            raise AIModelStateError("VALIDATION_FAILED")
        changed = _session(transaction).execute(
            update(AIModelRow).where(
                AIModelRow.ai_model_id == model_id,
                AIModelRow.model_state == before_state,
                AIModelRow.lock_version == expected_lock_version,
            ).values(model_state=state, lock_version=AIModelRow.lock_version + 1)
            .returning(AIModelRow.lock_version)
        ).scalar_one_or_none()
        if changed != expected_lock_version + 1:
            raise AIModelStateError("CONFLICT_VERSION")
        return changed

    def save(self, transaction: object, *, result: AIModelStateResult) -> None:
        if type(result) is not AIModelStateResult:
            raise AIModelStateError()
        result.__post_init__()
        _session(transaction).execute(insert(AIModelStateResultRow).values(
            state_result_id=result.result_id, ai_model_id=result.model_id,
            actor_id=result.actor_id, audit_event_id=result.audit_event_id,
            trace_id=result.trace_id, operation=result.operation,
            before_state=result.before_state, result_state=result.state,
            expected_lock_version=result.expected_lock_version,
            lock_version=result.lock_version,
        ))

    def get(self, transaction: object, *, result_id: uuid.UUID, model_id: uuid.UUID,
            actor_id: uuid.UUID, operation: str,
            expected_lock_version: int) -> AIModelStateResult | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                result_id, model_id, actor_id))
                or operation not in {"SUSPEND", "RETIRE"}
                or type(expected_lock_version) is not int or expected_lock_version < 0):
            raise AIModelStateError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.execute(select(AIModelStateResultRow).where(
            AIModelStateResultRow.state_result_id == result_id,
            AIModelStateResultRow.ai_model_id == model_id,
            AIModelStateResultRow.actor_id == actor_id,
            AIModelStateResultRow.operation == operation,
            AIModelStateResultRow.expected_lock_version == expected_lock_version,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if row is None:
            return None
        audit = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == row.audit_event_id,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        action = {"SUSPEND": "AI_MODEL_SUSPENDED", "RETIRE": "AI_MODEL_RETIRED"}[operation]
        if (audit is None or (audit.trace_id, audit.event_scope, audit.actor_type,
                              audit.actor_id, audit.action, audit.outcome,
                              audit.target_owner_module, audit.target_object_type,
                              audit.target_object_id, audit.target_version_id,
                              audit.before_state, audit.after_state) != (
                              row.trace_id, "DEPLOYMENT", "USER", row.actor_id,
                              action, "SUCCESS", "ai", "AI-02", row.ai_model_id,
                              None, row.before_state, row.result_state)):
            raise AIModelStateError()
        result = AIModelStateResult(
            row.state_result_id, row.ai_model_id, row.actor_id, row.audit_event_id,
            row.trace_id, row.operation, row.before_state, row.result_state,
            row.expected_lock_version, row.lock_version,
        )
        result.__post_init__()
        return result
