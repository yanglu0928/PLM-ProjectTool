"""Trace-owned atomic active-edge insert; no cross-module target reads."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from plm_assistant.modules.trace.application.create_link import StoredTraceLink
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape
from plm_assistant.modules.trace.infrastructure.orm import TraceLinkRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Trace transaction is required")
    return session


class SqlAlchemyTraceCreateRepository:
    def create_active(self, transaction: object, *, edge: TraceEdgeShape,
                      actor_id: uuid.UUID, trace_id: uuid.UUID) -> StoredTraceLink:
        if (type(edge) is not TraceEdgeShape
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(trace_id) is not uuid.UUID or trace_id.int == 0):
            raise ValueError("validated Trace edge and actor required")
        session = _session(transaction)
        identity = {
            "source_owner_module": edge.source.owner_module,
            "source_object_type": edge.source.object_type,
            "source_object_id": edge.source.object_id,
            "source_version_id": edge.source.version_id,
            "target_owner_module": edge.target.owner_module,
            "target_object_type": edge.target.object_type,
            "target_object_id": edge.target.object_id,
            "target_version_id": edge.target.version_id,
            "relation_type": edge.relation_type,
        }
        inserted = session.execute(
            pg_insert(TraceLinkRow).values(
                scope=edge.scope, project_id=edge.project_id,
                source_project_id=edge.source.project_id,
                target_project_id=edge.target.project_id,
                created_by=actor_id, trace_id=trace_id,
                **identity,
            ).on_conflict_do_nothing(
                index_elements=list(identity),
                index_where=TraceLinkRow.link_state == "ACTIVE",
            ).returning(TraceLinkRow.trace_link_id),
        ).scalar_one_or_none()
        if inserted is not None:
            return StoredTraceLink(inserted, True)
        existing = session.execute(
            select(TraceLinkRow.trace_link_id).where(
                TraceLinkRow.link_state == "ACTIVE",
                TraceLinkRow.scope == edge.scope,
                TraceLinkRow.project_id == edge.project_id,
                *(getattr(TraceLinkRow, field) == value
                  for field, value in identity.items()),
            ),
        ).scalar_one_or_none()
        if existing is None:
            raise RuntimeError("active Trace edge conflict could not be resolved")
        return StoredTraceLink(existing, False)
