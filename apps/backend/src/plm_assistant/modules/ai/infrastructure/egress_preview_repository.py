"""PostgreSQL Egress Preview route proof, immutable persistence, and safe projection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select

from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPersistenceRequest, EgressPreviewSourceView, EgressPreviewView, EgressRoute,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIEgressPreviewRow, AIEgressPreviewSourceRefRow,
)
from plm_assistant.modules.ai.infrastructure.model_orm import AIModelRow
from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow, AIProviderRow,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.platform.application.trace_context import new_uuid7


def _strings(value: object, *, maximum: int) -> tuple[str, ...]:
    if (type(value) is not list or not 1 <= len(value) <= maximum
            or len(set(value)) != len(value)
            or any(type(item) is not str or not 1 <= len(item) <= 64 or item != item.strip()
                   for item in value)):
        raise RuntimeError("invalid Egress Preview collection")
    return tuple(value)


class SqlAlchemyEgressPreviewRepository:
    def resolve_route(self, transaction: object, *, provider_id: uuid.UUID,
                      model_id: uuid.UUID) -> EgressRoute | None:
        if (type(provider_id) is not uuid.UUID or not provider_id.int
                or type(model_id) is not uuid.UUID or not model_id.int):
            return None
        row = _session(transaction).execute(
            select(
                AIProviderRow.ai_provider_id,
                AIProviderRow.provider_state,
                AIProviderConfigVersionRow.provider_config_version_id,
                AIProviderConfigVersionRow.data_region,
                AIProviderConfigVersionRow.egress_class,
                AIModelRow.ai_model_id,
                AIModelRow.model_state,
                AIModelRow.provider_model_key,
                AIModelRow.model_revision,
            ).select_from(AIProviderRow).join(
                AIProviderConfigVersionRow,
                (AIProviderConfigVersionRow.ai_provider_id == AIProviderRow.ai_provider_id)
                & (AIProviderConfigVersionRow.provider_config_version_id
                   == AIProviderRow.current_config_version_ref),
            ).join(
                AIModelRow,
                (AIModelRow.ai_provider_id == AIProviderRow.ai_provider_id)
                & (AIModelRow.ai_model_id == model_id),
            ).where(AIProviderRow.ai_provider_id == provider_id)
            .with_for_update(of=AIProviderRow)
            .execution_options(autoflush=False)
        ).one_or_none()
        if (row is None or row.provider_state != "ACTIVE" or row.model_state != "AVAILABLE"
                or row.egress_class != "EXTERNAL_APPROVAL_REQUIRED"):
            return None
        return EgressRoute(
            row.ai_provider_id, row.provider_config_version_id,
            row.ai_model_id, row.data_region, row.provider_model_key,
            row.model_revision,
        )

    def create(self, transaction: object, *,
               request: EgressPreviewPersistenceRequest) -> EgressPreviewView:
        if type(request) is not EgressPreviewPersistenceRequest:
            raise ValueError("invalid Egress Preview persistence request")
        session = _session(transaction)
        preview_id = uuid.UUID(new_uuid7())
        session.execute(insert(AIEgressPreviewRow).values(
            egress_preview_id=preview_id, scope="PROJECT", project_id=request.project_id,
            purpose_ref=request.purpose_ref, operation_type=request.operation_type,
            ai_provider_id=request.route.provider_id,
            provider_config_version_id=request.route.provider_config_version_id,
            ai_model_id=request.route.model_id, data_region=request.route.data_region,
            allowed_data_categories=list(request.allowed_data_categories),
            minimal_payload_policy_ref=request.minimal_payload_policy_ref,
            estimated_record_count=request.estimated_record_count,
            max_payload_bytes=request.max_payload_bytes,
            max_input_tokens=request.max_input_tokens,
            max_retry_attempts=request.max_retry_attempts,
            payload_fingerprint=request.payload_fingerprint,
            source_refs_fingerprint=request.source_refs_fingerprint,
            risk_codes=list(request.risk_codes), created_by=request.created_by,
            trace_id=request.trace_id, expires_at=request.expires_at,
        ))
        for ordinal, item in enumerate(request.sources, 1):
            session.execute(insert(AIEgressPreviewSourceRefRow).values(
                egress_preview_id=preview_id, ref_ordinal=ordinal,
                resource_type=item.resource_type, owner_module=item.owner_module,
                object_type=item.object_type, object_id=item.object_id,
                version_id=item.version_id, scope=item.scope, project_id=item.project_id,
            ))
        session.flush()
        view = self.get(transaction, preview_id=preview_id, project_id=request.project_id)
        if view is None:
            raise RuntimeError("Egress Preview write was not visible")
        return view

    def get(self, transaction: object, *, preview_id: uuid.UUID,
            project_id: uuid.UUID) -> EgressPreviewView | None:
        if (type(preview_id) is not uuid.UUID or not preview_id.int
                or type(project_id) is not uuid.UUID or not project_id.int):
            return None
        session = _session(transaction)
        root = session.execute(
            select(AIEgressPreviewRow).where(
                AIEgressPreviewRow.egress_preview_id == preview_id,
                AIEgressPreviewRow.scope == "PROJECT",
                AIEgressPreviewRow.project_id == project_id,
            ).execution_options(autoflush=False)
        ).scalar_one_or_none()
        if root is None:
            return None
        rows = session.execute(
            select(AIEgressPreviewSourceRefRow).where(
                AIEgressPreviewSourceRefRow.egress_preview_id == preview_id,
                AIEgressPreviewSourceRefRow.scope == "PROJECT",
                AIEgressPreviewSourceRefRow.project_id == project_id,
            ).order_by(AIEgressPreviewSourceRefRow.ref_ordinal)
            .execution_options(autoflush=False)
        ).scalars().all()
        if (not rows or any(row.ref_ordinal != index for index, row in enumerate(rows, 1))
                or any(type(value) is not uuid.UUID or not value.int for value in (
                    root.egress_preview_id, root.project_id, root.ai_provider_id,
                    root.provider_config_version_id, root.ai_model_id,
                ))
                or type(root.payload_fingerprint) is not bytes
                or len(root.payload_fingerprint) != 32
                or type(root.source_refs_fingerprint) is not bytes
                or len(root.source_refs_fingerprint) != 32
                or not isinstance(root.created_at, datetime) or root.created_at.tzinfo is None
                or not isinstance(root.expires_at, datetime) or root.expires_at.tzinfo is None):
            raise RuntimeError("invalid Egress Preview history")
        return EgressPreviewView(
            root.egress_preview_id, root.project_id, root.purpose_ref, root.operation_type,
            root.ai_provider_id, root.provider_config_version_id, root.ai_model_id,
            root.data_region, _strings(root.allowed_data_categories, maximum=64),
            tuple(EgressPreviewSourceView(
                row.resource_type, row.object_id, row.version_id,
            ) for row in rows),
            root.minimal_payload_policy_ref, root.estimated_record_count,
            root.max_payload_bytes, root.max_input_tokens, root.max_retry_attempts,
            bytes(root.payload_fingerprint), bytes(root.source_refs_fingerprint),
            _strings(root.risk_codes, maximum=32), root.created_at, root.expires_at,
        )
