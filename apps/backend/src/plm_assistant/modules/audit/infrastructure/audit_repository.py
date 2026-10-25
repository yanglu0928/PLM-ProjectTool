"""SQLAlchemy append adapter; never opens, commits or rolls back a transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import insert
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow


class AuditTransactionError(RuntimeError):
    """The caller did not supply an active SQLAlchemy transaction."""


class SqlAlchemyAuditRepository:
    def append(self, transaction: object, event: AuditEventDraft) -> uuid.UUID:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as exc:
            raise AuditTransactionError("active audit transaction is required") from exc
        if not isinstance(session, Session) or not session.in_transaction():
            raise AuditTransactionError("active audit transaction is required")
        statement = insert(AuditEventRow).values(
            trace_id=event.trace_id,
            event_scope=event.event_scope,
            target_project_id=event.target_project_id,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            original_actor_id=event.original_actor_id,
            actor_hint_digest=event.actor_hint_digest,
            action=event.action,
            outcome=event.outcome,
            target_owner_module=event.target_owner_module,
            target_object_type=event.target_object_type,
            target_object_id=event.target_object_id,
            target_version_id=event.target_version_id,
            reason_code=event.reason_code,
            before_state=event.before_state,
            after_state=event.after_state,
        ).returning(AuditEventRow.audit_event_id)
        return session.execute(statement).scalar_one()
