"""Project-scoped active Trace adjacency; never authorizes endpoint visibility."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from .orm import TraceLinkRow


class SqlAlchemyTraceAdjacencyRepository:
    def adjacent(self, transaction: object, *, project_id: uuid.UUID,
                 root: TraceVersionRef, direction: str, relation_type: str | None,
                 limit: int) -> tuple[TraceAdjacency, ...]:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(root) is not TraceVersionRef
                or direction not in ("UPSTREAM", "DOWNSTREAM")
                or type(limit) is not int or not 1 <= limit <= 101):
            raise ValueError("bounded Trace query required")
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Trace transaction required")
        prefix = "target" if direction == "UPSTREAM" else "source"
        predicates = [
            TraceLinkRow.link_state == "ACTIVE",
            TraceLinkRow.scope == "PROJECT",
            TraceLinkRow.project_id == project_id,
            getattr(TraceLinkRow, f"{prefix}_owner_module") == root.owner_module,
            getattr(TraceLinkRow, f"{prefix}_object_type") == root.object_type,
            getattr(TraceLinkRow, f"{prefix}_object_id") == root.object_id,
            getattr(TraceLinkRow, f"{prefix}_version_id") == root.version_id,
            getattr(TraceLinkRow, f"{prefix}_project_id") == root.project_id,
        ]
        if relation_type is not None:
            predicates.append(TraceLinkRow.relation_type == relation_type)
        rows = session.execute(
            select(TraceLinkRow).where(*predicates).order_by(
                TraceLinkRow.created_at, TraceLinkRow.trace_link_id,
            ).limit(limit),
        ).scalars().all()
        return tuple(TraceAdjacency(
            row.trace_link_id,
            TraceEdgeShape(
                TraceVersionRef(row.source_owner_module, row.source_object_type,
                                row.source_object_id, row.source_version_id,
                                "GLOBAL" if row.source_project_id is None else "PROJECT",
                                row.source_project_id),
                TraceVersionRef(row.target_owner_module, row.target_object_type,
                                row.target_object_id, row.target_version_id,
                                "PROJECT", row.target_project_id),
                row.relation_type, row.scope, row.project_id,
            ),
        ) for row in rows)
