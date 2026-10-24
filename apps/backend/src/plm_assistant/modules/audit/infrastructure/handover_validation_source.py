"""Audit-owned immutable replay proof for Handover validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.handover.application.validate_version import HandoverValidationAudit


class SqlAlchemyHandoverValidationAuditSource:
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            handover_analysis_version_id: uuid.UUID) -> HandoverValidationAudit | None:
        values = (audit_event_id, actor_id, project_id, handover_analysis_version_id)
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Audit transaction required") from error
        row = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == audit_event_id,
            AuditEventRow.event_scope == "PROJECT",
            AuditEventRow.target_project_id == project_id,
            AuditEventRow.actor_type == "USER",
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.action == "HND_VERSION_VALIDATED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "handover",
            AuditEventRow.target_object_type == "HND-02",
            AuditEventRow.target_object_id == handover_analysis_version_id,
            AuditEventRow.target_version_id == handover_analysis_version_id,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None or row.reason_code is None:
            return None
        return HandoverValidationAudit(
            row.audit_event_id, row.trace_id, row.occurred_at, row.reason_code,
        )
