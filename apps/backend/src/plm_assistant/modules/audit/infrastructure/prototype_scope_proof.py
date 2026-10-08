"""Read immutable Audit action matching a Prototype scope decision."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.application.prototype_scope_proof import (
    PrototypeScopeDecisionAuditProof,
)

from .audit_orm import AuditEventRow


class SqlAlchemyPrototypeScopeDecisionAuditProof:
    def prove_user_action(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID, confirmed_by: uuid.UUID,
        decided_at: datetime,
    ) -> PrototypeScopeDecisionAuditProof | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                project_id, prototype_id, confirmed_by))
                or type(decided_at) is not datetime
                or decided_at.tzinfo is None
                or decided_at.utcoffset() is None):
            return None
        decided_utc = decided_at.astimezone(timezone.utc)
        try:
            session = transaction.session
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Audit transaction required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Audit transaction required")
        rows = tuple(session.execute(select(AuditEventRow).where(
            AuditEventRow.event_scope == "PROJECT",
            AuditEventRow.target_project_id == project_id,
            AuditEventRow.actor_type == "USER",
            AuditEventRow.actor_id == confirmed_by,
            AuditEventRow.action == "PROTOTYPE_MARKED_NOT_REQUIRED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "prototype",
            AuditEventRow.target_object_type == "PRT-02",
            AuditEventRow.target_object_id == prototype_id,
            AuditEventRow.target_version_id.is_(None),
            AuditEventRow.before_state == "ACTIVE",
            AuditEventRow.after_state == "NOT_REQUIRED",
            AuditEventRow.occurred_at >= decided_utc,
        ).order_by(
            AuditEventRow.occurred_at,
            AuditEventRow.audit_event_id,
        ).limit(2).with_for_update(
            read=True, of=AuditEventRow,
        ).execution_options(populate_existing=True)).scalars())
        if len(rows) != 1:
            return None
        row = rows[0]
        if (type(row.occurred_at) is not datetime
                or row.occurred_at.tzinfo is None
                or row.occurred_at.utcoffset() is None):
            return None
        occurred_utc = row.occurred_at.astimezone(timezone.utc)
        if not timedelta(0) <= occurred_utc - decided_utc <= timedelta(minutes=5):
            return None
        return PrototypeScopeDecisionAuditProof(
            row.audit_event_id, project_id, prototype_id,
            confirmed_by, occurred_utc,
        )
