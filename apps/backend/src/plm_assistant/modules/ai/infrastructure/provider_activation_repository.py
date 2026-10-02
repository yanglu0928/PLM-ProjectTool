"""AI-owned atomic state transition and immutable first activation response."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update

from plm_assistant.modules.ai.application.activate_provider import (
    AIProviderActivationError, ActivatedAIProvider,
)
from plm_assistant.modules.ai.application.provider_activation_proof import ProviderActivationProof
from plm_assistant.modules.ai.infrastructure.provider_create_repository import _session
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderActivationResultRow, AIProviderRow,
)
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow


class SqlAlchemyAIProviderActivationRepository:
    def activate(self, transaction: object, *, proof: ProviderActivationProof,
                 expected_lock_version: int) -> int:
        if (type(proof) is not ProviderActivationProof
                or proof.state not in ("CONFIGURED", "SUSPENDED")
                or type(expected_lock_version) is not int
                or expected_lock_version != proof.lock_version):
            raise AIProviderActivationError()
        changed = _session(transaction).execute(
            update(AIProviderRow).where(
                AIProviderRow.ai_provider_id == proof.provider_id,
                AIProviderRow.current_config_version_ref == proof.config_id,
                AIProviderRow.lock_version == expected_lock_version,
                AIProviderRow.provider_state == proof.state,
            ).values(provider_state="ACTIVE",
                     lock_version=AIProviderRow.lock_version + 1)
            .returning(AIProviderRow.lock_version)
        ).scalar_one_or_none()
        if changed != expected_lock_version + 1:
            raise AIProviderActivationError("CONFLICT_VERSION")
        return changed

    def save(self, transaction: object, *, result: ActivatedAIProvider) -> None:
        if type(result) is not ActivatedAIProvider:
            raise AIProviderActivationError()
        result.__post_init__()
        _session(transaction).execute(insert(AIProviderActivationResultRow).values(
            activation_result_id=result.activation_result_id,
            ai_provider_id=result.provider_id,
            provider_config_version_id=result.config_id,
            probe_result_id=result.proof_result_id,
            actor_id=result.actor_id, audit_event_id=result.audit_event_id,
            trace_id=result.trace_id, before_state=result.before_state,
            result_state=result.state,
            expected_lock_version=result.expected_lock_version,
            lock_version=result.lock_version,
        ))

    def get(self, transaction: object, *, result_id: uuid.UUID, provider_id: uuid.UUID,
            actor_id: uuid.UUID, expected_lock_version: int) -> ActivatedAIProvider | None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                result_id, provider_id, actor_id))
                or type(expected_lock_version) is not int
                or expected_lock_version < 0):
            raise AIProviderActivationError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.execute(select(AIProviderActivationResultRow).where(
            AIProviderActivationResultRow.activation_result_id == result_id,
            AIProviderActivationResultRow.ai_provider_id == provider_id,
            AIProviderActivationResultRow.actor_id == actor_id,
            AIProviderActivationResultRow.expected_lock_version == expected_lock_version,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if row is None:
            return None
        audit = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == row.audit_event_id,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if (audit is None or (audit.trace_id, audit.event_scope, audit.actor_type,
                              audit.actor_id, audit.action, audit.outcome,
                              audit.target_owner_module, audit.target_object_type,
                              audit.target_object_id, audit.target_version_id,
                              audit.before_state, audit.after_state) != (
                              row.trace_id, "DEPLOYMENT", "USER", row.actor_id,
                              "AI_PROVIDER_ACTIVATED", "SUCCESS", "ai", "AI-01",
                              row.ai_provider_id, row.provider_config_version_id,
                              row.before_state, "ACTIVE")):
            raise AIProviderActivationError()
        result = ActivatedAIProvider(
            row.activation_result_id, row.ai_provider_id,
            row.provider_config_version_id, row.probe_result_id,
            row.actor_id, row.audit_event_id, row.trace_id,
            row.before_state, row.expected_lock_version,
            row.lock_version, row.result_state,
        )
        result.__post_init__()
        return result
