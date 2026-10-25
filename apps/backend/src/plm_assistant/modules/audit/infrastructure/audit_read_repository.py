"""Fixed-shape, scope-filtered AuditEvent queries."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select, tuple_
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.application.queries.audit_query import (
    AuditEventView, AuditPage, AuditPosition, AuditSearch,
)
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.audit.infrastructure.audit_repository import AuditTransactionError


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise AuditTransactionError("active audit transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise AuditTransactionError("active audit transaction is required")
    return session


def _scope(project_id: uuid.UUID | None):
    if project_id is None:
        return and_(AuditEventRow.event_scope == "DEPLOYMENT", AuditEventRow.target_project_id.is_(None))
    return and_(AuditEventRow.event_scope == "PROJECT", AuditEventRow.target_project_id == project_id)


def _view(row: AuditEventRow) -> AuditEventView:
    return AuditEventView(
        audit_event_id=row.audit_event_id, occurred_at=row.occurred_at,
        trace_id=row.trace_id, event_scope=row.event_scope,
        target_project_id=row.target_project_id, actor_type=row.actor_type,
        actor_id=row.actor_id, original_actor_id=row.original_actor_id,
        action=row.action, outcome=row.outcome,
        target_owner_module=row.target_owner_module, target_object_type=row.target_object_type,
        target_object_id=row.target_object_id, target_version_id=row.target_version_id,
        reason_code=row.reason_code, before_state=row.before_state, after_state=row.after_state,
    )


class SqlAlchemyAuditReadRepository:
    def list_events(self, transaction: object, *, project_id: uuid.UUID | None, search: AuditSearch) -> AuditPage:
        session = _session(transaction)
        statement = select(AuditEventRow).where(
            _scope(project_id), AuditEventRow.occurred_at >= search.start_at,
            AuditEventRow.occurred_at < search.end_at,
        )
        if search.after is not None:
            statement = statement.where(
                tuple_(AuditEventRow.occurred_at, AuditEventRow.audit_event_id)
                < (search.after.occurred_at, search.after.audit_event_id)
            )
        for column, value in (
            (AuditEventRow.action, search.action),
            (AuditEventRow.outcome, search.outcome),
            (AuditEventRow.actor_id, search.actor_id),
            (AuditEventRow.target_object_type, search.target_object_type),
            (AuditEventRow.target_object_id, search.target_object_id),
            (AuditEventRow.trace_id, search.trace_id),
        ):
            if value is not None:
                statement = statement.where(column == value)
        rows = session.scalars(
            statement.order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.audit_event_id.desc())
            .limit(search.page_size + 1)
        ).all()
        has_more = len(rows) > search.page_size
        visible = rows[:search.page_size]
        items = tuple(_view(row) for row in visible)
        last = visible[-1] if has_more else None
        return AuditPage(
            items=items,
            next_position=AuditPosition(last.occurred_at, last.audit_event_id) if last else None,
            has_more=has_more,
        )

    def get_event(self, transaction: object, *, project_id: uuid.UUID | None, event_id: uuid.UUID) -> AuditEventView | None:
        row = _session(transaction).scalar(
            select(AuditEventRow).where(_scope(project_id), AuditEventRow.audit_event_id == event_id)
        )
        return _view(row) if row is not None else None
