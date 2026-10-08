"""Audit-owned immutable replay proof for PrototypeVersion validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeValidationAudit,
)

from .audit_orm import AuditEventRow


class SqlAlchemyPrototypeValidationAuditSource:
    def get(
        self, transaction: object, *, audit_event_id: uuid.UUID,
        actor_id: uuid.UUID, project_id: uuid.UUID,
        prototype_version_id: uuid.UUID,
    ) -> PrototypeValidationAudit | None:
        values = (
            audit_event_id, actor_id, project_id, prototype_version_id,
        )
        if any(type(value) is not uuid.UUID or value.int == 0
               for value in values):
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
            AuditEventRow.action == "PROTOTYPE_VERSION_VALIDATED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "prototype",
            AuditEventRow.target_object_type == "PRT-03",
            AuditEventRow.target_object_id == prototype_version_id,
            AuditEventRow.target_version_id == prototype_version_id,
            AuditEventRow.before_state == AuditEventRow.after_state,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None or row.reason_code is None or row.before_state is None:
            return None
        return PrototypeValidationAudit(
            row.audit_event_id, row.trace_id, row.occurred_at,
            row.reason_code, row.before_state,
        )
