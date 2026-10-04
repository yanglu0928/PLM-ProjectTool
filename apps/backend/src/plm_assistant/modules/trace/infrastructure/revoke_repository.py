"""Trace-owned locked PROJECT relationship revocation."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.trace.application.revoke_link import TraceLinkState
from plm_assistant.modules.trace.infrastructure.orm import TraceLinkRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Trace transaction is required")
    return session


class SqlAlchemyTraceRevokeRepository:
    def lock(self, transaction: object, *, project_id: uuid.UUID,
             trace_link_id: uuid.UUID) -> TraceLinkState | None:
        row = _session(transaction).execute(
            select(TraceLinkRow).where(
                TraceLinkRow.scope == "PROJECT",
                TraceLinkRow.project_id == project_id,
                TraceLinkRow.trace_link_id == trace_link_id,
            ).with_for_update().execution_options(populate_existing=True),
        ).scalar_one_or_none()
        if row is None:
            return None
        return TraceLinkState(
            row.trace_link_id, row.project_id, row.link_state, row.lock_version,
        )

    def revoke(self, transaction: object, *, project_id: uuid.UUID,
               trace_link_id: uuid.UUID, expected_version: int) -> int:
        version = _session(transaction).execute(
            update(TraceLinkRow).where(
                TraceLinkRow.scope == "PROJECT",
                TraceLinkRow.project_id == project_id,
                TraceLinkRow.trace_link_id == trace_link_id,
                TraceLinkRow.link_state == "ACTIVE",
                TraceLinkRow.lock_version == expected_version,
            ).values(link_state="REVOKED").returning(TraceLinkRow.lock_version),
        ).scalar_one_or_none()
        if version is None:
            raise RuntimeError("locked TraceLink transition was lost")
        return version
