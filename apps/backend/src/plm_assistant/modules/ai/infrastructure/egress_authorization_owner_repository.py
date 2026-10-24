"""Locked current Egress Authorization projection with live route proof."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.infrastructure.egress_authorization_repository import (
    egress_authorization_view,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import AIEgressAuthorizationRow
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.ai.infrastructure.provider_orm import AIProviderRow
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session


class SqlAlchemyEgressAuthorizationOwnerRepository:
    def resolve_current(self, transaction: object, *, authorization_ref: uuid.UUID,
                        project_id: uuid.UUID):
        if (type(authorization_ref) is not uuid.UUID or not authorization_ref.int
                or type(project_id) is not uuid.UUID or not project_id.int):
            return None
        row = _session(transaction).execute(
            select(AIEgressAuthorizationRow).join(
                AIProviderRow,
                AIProviderRow.ai_provider_id == AIEgressAuthorizationRow.ai_provider_id,
            ).join(
                AIModelRow,
                (AIModelRow.ai_model_id == AIEgressAuthorizationRow.ai_model_id)
                & (AIModelRow.ai_provider_id == AIEgressAuthorizationRow.ai_provider_id),
            ).where(
                AIEgressAuthorizationRow.authorization_id == authorization_ref,
                AIEgressAuthorizationRow.scope == "PROJECT",
                AIEgressAuthorizationRow.project_id == project_id,
                AIEgressAuthorizationRow.operation_type == "AI_TASK",
                AIEgressAuthorizationRow.authorization_state == "AUTHORIZED",
                AIEgressAuthorizationRow.lock_version == 0,
                AIProviderRow.provider_state == "ACTIVE",
                AIProviderRow.current_config_version_ref
                == AIEgressAuthorizationRow.provider_config_version_id,
                AIModelRow.model_state == "AVAILABLE",
            ).with_for_update(of=AIEgressAuthorizationRow)
            .execution_options(autoflush=False)
        ).scalar_one_or_none()
        return None if row is None else egress_authorization_view(row)
