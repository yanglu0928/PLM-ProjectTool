"""Audit-owned immutable source for Capability validation idempotent replay."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.capability.application.validate_version import (
    CapabilityValidationAudit,
)

from .audit_orm import AuditEventRow


class SqlAlchemyCapabilityValidationAuditSource:
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID,
            baseline_version_id: uuid.UUID) -> CapabilityValidationAudit | None:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Audit transaction required") from error
        row = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == audit_event_id,
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.action == "CAP_VERSION_VALIDATED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "capability",
            AuditEventRow.target_object_type == "CAP-02",
            AuditEventRow.target_object_id == baseline_version_id,
            AuditEventRow.target_version_id == baseline_version_id,
            AuditEventRow.before_state == AuditEventRow.after_state,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None or row.reason_code is None:
            return None
        return CapabilityValidationAudit(
            row.audit_event_id, row.trace_id, row.occurred_at, row.reason_code,
        )
