"""PostgreSQL persistence for Egress Authorization and revocation history."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update

from plm_assistant.modules.ai.application.egress_authorization import (
    EgressAuthorizationCreate, EgressAuthorizationView, EgressAuthorizeResult,
    EgressRevokeResult,
)
from plm_assistant.modules.ai.infrastructure.egress_orm import (
    AIEgressAuthorizationRevocationRow, AIEgressAuthorizationRow,
    AIEgressAuthorizeResultRow, AIEgressPreviewRow, AIEgressRevokeResultRow,
)
from plm_assistant.modules.ai.infrastructure.egress_preview_repository import (
    SqlAlchemyEgressPreviewRepository,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.platform.application.trace_context import new_uuid7


def _categories(value: object) -> tuple[str, ...]:
    if (type(value) is not list or not 1 <= len(value) <= 64
            or len(set(value)) != len(value)
            or any(type(item) is not str or not item or item != item.strip()
                   or len(item) > 64 for item in value)):
        raise RuntimeError("invalid Egress Authorization categories")
    return tuple(value)


def egress_authorization_view(row: AIEgressAuthorizationRow, *, state: str | None = None,
                              lock_version: int | None = None) -> EgressAuthorizationView:
    identifiers = (
        row.authorization_id, row.egress_preview_id, row.project_id,
        row.ai_provider_id, row.provider_config_version_id,
        row.ai_model_id, row.approved_by,
    )
    if (any(type(value) is not uuid.UUID or not value.int for value in identifiers)
            or type(row.payload_fingerprint) is not bytes
            or len(row.payload_fingerprint) != 32
            or type(row.source_refs_fingerprint) is not bytes
            or len(row.source_refs_fingerprint) != 32
            or (row.content_plan_ref is not None
                and (type(row.content_plan_ref) is not uuid.UUID
                     or not row.content_plan_ref.int))
            or row.approved_role not in ("ProjectManager", "CustomerManager")
            or row.authorization_state not in ("AUTHORIZED", "REVOKED")
            or row.lock_version not in (0, 1)
            or not isinstance(row.approved_at, datetime)
            or row.approved_at.tzinfo is None
            or not isinstance(row.valid_until, datetime)
            or row.valid_until.tzinfo is None):
        raise RuntimeError("invalid Egress Authorization history")
    projected_state = row.authorization_state if state is None else state
    projected_version = row.lock_version if lock_version is None else lock_version
    if projected_state not in ("AUTHORIZED", "REVOKED") or projected_version not in (0, 1):
        raise RuntimeError("invalid Egress Authorization projection")
    return EgressAuthorizationView(
        row.authorization_id, row.egress_preview_id, row.project_id,
        row.purpose_ref, row.operation_type, row.ai_provider_id,
        row.provider_config_version_id, row.ai_model_id, row.data_region,
        _categories(row.allowed_data_categories), row.minimal_payload_policy_ref,
        row.max_record_count, row.max_payload_bytes, row.max_input_tokens,
        row.max_retry_attempts, bytes(row.payload_fingerprint),
        bytes(row.source_refs_fingerprint), row.approved_by, row.approved_role,
        row.approved_at, row.valid_until, projected_state, projected_version,
        row.content_plan_ref,
    )


class SqlAlchemyEgressAuthorizationRepository:
    def __init__(self) -> None:
        self._previews = SqlAlchemyEgressPreviewRepository()

    def preview_for_authorize(self, transaction: object, *, preview_id: uuid.UUID,
                              project_id: uuid.UUID):
        session = _session(transaction)
        locked = session.execute(
            select(AIEgressPreviewRow.egress_preview_id).where(
                AIEgressPreviewRow.egress_preview_id == preview_id,
                AIEgressPreviewRow.scope == "PROJECT",
                AIEgressPreviewRow.project_id == project_id,
            ).with_for_update().execution_options(autoflush=False)
        ).scalar_one_or_none()
        if locked is None:
            return None
        return self._previews.get(
            transaction, preview_id=preview_id, project_id=project_id,
        )

    def create_authorization(self, transaction: object, *,
                             request: EgressAuthorizationCreate) -> EgressAuthorizationView:
        if type(request) is not EgressAuthorizationCreate:
            raise ValueError("invalid Egress Authorization request")
        session = _session(transaction)
        preview = request.preview
        session.execute(insert(AIEgressAuthorizationRow).values(
            authorization_id=request.authorization_id,
            egress_preview_id=preview.preview_id, scope="PROJECT",
            project_id=preview.project_id, purpose_ref=preview.purpose_ref,
            operation_type=preview.operation_type,
            ai_provider_id=preview.provider_id,
            provider_config_version_id=preview.provider_config_version_id,
            ai_model_id=preview.model_id, data_region=preview.data_region,
            allowed_data_categories=list(request.allowed_data_categories),
            minimal_payload_policy_ref=preview.minimal_payload_policy_ref,
            max_record_count=request.max_record_count,
            max_payload_bytes=request.max_payload_bytes,
            max_input_tokens=request.max_input_tokens,
            max_retry_attempts=request.max_retry_attempts,
            payload_fingerprint=preview.payload_fingerprint,
            source_refs_fingerprint=preview.source_refs_fingerprint,
            content_plan_ref=preview.content_plan_ref,
            authorization_state="AUTHORIZED", approved_by=request.approved_by,
            approved_role=request.approved_role, valid_until=request.valid_until,
            lock_version=0,
        ))
        session.flush()
        row = session.execute(
            select(AIEgressAuthorizationRow).where(
                AIEgressAuthorizationRow.authorization_id == request.authorization_id,
            ).execution_options(autoflush=False)
        ).scalar_one()
        return egress_authorization_view(row)

    def save_authorize_result(self, transaction: object, *, result_id: uuid.UUID,
                              authorization: EgressAuthorizationView,
                              audit_event_id: uuid.UUID, trace_id: uuid.UUID) -> None:
        _session(transaction).execute(insert(AIEgressAuthorizeResultRow).values(
            result_id=result_id, authorization_id=authorization.authorization_id,
            egress_preview_id=authorization.preview_id,
            actor_id=authorization.approved_by,
            approved_role=authorization.approved_role,
            audit_event_id=audit_event_id, trace_id=trace_id,
            result_state="AUTHORIZED", lock_version=0,
            approved_at=authorization.approved_at,
            valid_until=authorization.valid_until,
        ))

    def get_authorize_result(self, transaction: object, *, result_id: uuid.UUID,
                             preview_id: uuid.UUID, project_id: uuid.UUID,
                             actor_id: uuid.UUID) -> EgressAuthorizeResult | None:
        row = _session(transaction).execute(
            select(AIEgressAuthorizeResultRow, AIEgressAuthorizationRow).join(
                AIEgressAuthorizationRow,
                AIEgressAuthorizationRow.authorization_id
                == AIEgressAuthorizeResultRow.authorization_id,
            ).where(
                AIEgressAuthorizeResultRow.result_id == result_id,
                AIEgressAuthorizeResultRow.egress_preview_id == preview_id,
                AIEgressAuthorizeResultRow.actor_id == actor_id,
                AIEgressAuthorizationRow.project_id == project_id,
            ).execution_options(autoflush=False)
        ).one_or_none()
        if row is None:
            return None
        result, root = row
        if (result.result_state != "AUTHORIZED" or result.lock_version != 0
                or result.approved_at != root.approved_at
                or result.valid_until != root.valid_until
                or result.actor_id != root.approved_by
                or result.approved_role != root.approved_role):
            raise RuntimeError("invalid Egress authorize result history")
        authorization = egress_authorization_view(
            root, state="AUTHORIZED", lock_version=0,
        )
        return EgressAuthorizeResult(
            result.result_id, authorization, result.audit_event_id, result.trace_id,
        )

    def authorization_for_revoke(self, transaction: object, *, authorization_id: uuid.UUID,
                                 project_id: uuid.UUID) -> EgressAuthorizationView | None:
        row = _session(transaction).execute(
            select(AIEgressAuthorizationRow).where(
                AIEgressAuthorizationRow.authorization_id == authorization_id,
                AIEgressAuthorizationRow.scope == "PROJECT",
                AIEgressAuthorizationRow.project_id == project_id,
            ).with_for_update().execution_options(autoflush=False)
        ).scalar_one_or_none()
        return None if row is None else egress_authorization_view(row)

    def revoke(self, transaction: object, *, authorization: EgressAuthorizationView,
               actor_id: uuid.UUID, revoked_role: str, reason_code: str,
               reason_summary: str, audit_event_id: uuid.UUID,
               trace_id: uuid.UUID) -> EgressRevokeResult:
        session = _session(transaction)
        revocation_id, result_id = uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7())
        session.execute(insert(AIEgressAuthorizationRevocationRow).values(
            revocation_id=revocation_id,
            authorization_id=authorization.authorization_id,
            revoked_by=actor_id, revoked_role=revoked_role,
            reason_code=reason_code, reason_summary=reason_summary,
            audit_event_id=audit_event_id, trace_id=trace_id,
        ))
        session.flush()
        revocation = session.execute(
            select(AIEgressAuthorizationRevocationRow).where(
                AIEgressAuthorizationRevocationRow.revocation_id == revocation_id,
            ).execution_options(autoflush=False)
        ).scalar_one()
        changed = session.execute(update(AIEgressAuthorizationRow).where(
            AIEgressAuthorizationRow.authorization_id == authorization.authorization_id,
            AIEgressAuthorizationRow.authorization_state == "AUTHORIZED",
            AIEgressAuthorizationRow.lock_version == authorization.lock_version,
        ).values(authorization_state="REVOKED", lock_version=1))
        if changed.rowcount != 1:
            raise RuntimeError("Egress Authorization revoke conflict")
        session.execute(insert(AIEgressRevokeResultRow).values(
            result_id=result_id, authorization_id=authorization.authorization_id,
            revocation_id=revocation_id, actor_id=actor_id,
            revoked_role=revoked_role, audit_event_id=audit_event_id,
            trace_id=trace_id, result_state="REVOKED", lock_version=1,
            revoked_at=revocation.revoked_at,
        ))
        return EgressRevokeResult(
            result_id, authorization.authorization_id, revocation_id,
            actor_id, revoked_role, audit_event_id, trace_id,
            "REVOKED", 1, revocation.revoked_at,
        )

    def get_revoke_result(self, transaction: object, *, result_id: uuid.UUID,
                          authorization_id: uuid.UUID, project_id: uuid.UUID,
                          actor_id: uuid.UUID) -> EgressRevokeResult | None:
        row = _session(transaction).execute(
            select(AIEgressRevokeResultRow, AIEgressAuthorizationRow).join(
                AIEgressAuthorizationRow,
                AIEgressAuthorizationRow.authorization_id
                == AIEgressRevokeResultRow.authorization_id,
            ).where(
                AIEgressRevokeResultRow.result_id == result_id,
                AIEgressRevokeResultRow.authorization_id == authorization_id,
                AIEgressRevokeResultRow.actor_id == actor_id,
                AIEgressAuthorizationRow.project_id == project_id,
            ).execution_options(autoflush=False)
        ).one_or_none()
        if row is None:
            return None
        result, root = row
        if (root.authorization_state != "REVOKED" or root.lock_version != 1
                or result.result_state != "REVOKED" or result.lock_version != 1):
            raise RuntimeError("invalid Egress revoke result history")
        return EgressRevokeResult(
            result.result_id, result.authorization_id, result.revocation_id,
            result.actor_id, result.revoked_role, result.audit_event_id,
            result.trace_id, result.result_state, result.lock_version,
            result.revoked_at,
        )
