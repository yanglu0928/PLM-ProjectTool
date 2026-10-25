"""Audit-owned immutable first observation for SectionVersion validation replay."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.solution.application.section_version_validation_contract import AUDIT_ACTION
from plm_assistant.modules.solution.application.validate_section_version import (
    SectionVersionValidationAudit,
)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class SqlAlchemySectionVersionValidationAuditSource:
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionValidationAudit | None:
        if not all(_id(value) for value in (
                audit_event_id, actor_id, project_id, section_id, version_id)):
            return None
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active validation Audit transaction required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active validation Audit transaction required")
        row = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == audit_event_id,
            AuditEventRow.event_scope == "PROJECT",
            AuditEventRow.target_project_id == project_id,
            AuditEventRow.actor_type == "USER",
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.action == AUDIT_ACTION,
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "solution",
            AuditEventRow.target_object_type == "SOL-05",
            AuditEventRow.target_object_id == section_id,
            AuditEventRow.target_version_id == version_id,
            AuditEventRow.before_state == AuditEventRow.after_state,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None or row.reason_code is None or row.before_state is None:
            return None
        return SectionVersionValidationAudit(
            row.audit_event_id, row.trace_id, row.occurred_at,
            row.reason_code, row.before_state)
