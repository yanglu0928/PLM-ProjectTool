"""Audit-owned immutable replay proof for RequirementVersion validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.requirement.application.validate_version import (
    RequirementValidationAudit,
)

from .audit_orm import AuditEventRow


class SqlAlchemyRequirementValidationAuditSource:
    def get(
        self, transaction: object, *, audit_event_id: uuid.UUID,
        actor_id: uuid.UUID, project_id: uuid.UUID,
        requirement_version_id: uuid.UUID,
    ) -> RequirementValidationAudit | None:
        values = (audit_event_id, actor_id, project_id, requirement_version_id)
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
            AuditEventRow.action == "REQUIREMENT_VERSION_VALIDATED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "requirement",
            AuditEventRow.target_object_type == "REQ-03",
            AuditEventRow.target_object_id == requirement_version_id,
            AuditEventRow.target_version_id == requirement_version_id,
            AuditEventRow.before_state == AuditEventRow.after_state,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None or row.reason_code is None:
            return None
        return RequirementValidationAudit(
            row.audit_event_id, row.trace_id, row.occurred_at, row.reason_code,
        )
