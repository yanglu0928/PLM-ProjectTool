"""Read-lock an ACTIVE project TraceLink for resolution proof."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef

from .orm import TraceLinkRow


class SqlAlchemyTraceResolutionRepository:
    def active_project_edge(self, transaction: object, *, project_id: uuid.UUID,
                            trace_link_id: uuid.UUID) -> TraceEdgeShape | None:
        session = transaction.session  # type: ignore[attr-defined]
        row = session.execute(select(TraceLinkRow).where(
            TraceLinkRow.trace_link_id == trace_link_id,
            TraceLinkRow.project_id == project_id,
            TraceLinkRow.scope == "PROJECT",
            TraceLinkRow.link_state == "ACTIVE",
        ).with_for_update(of=TraceLinkRow, read=True)).scalar_one_or_none()
        if row is None:
            return None
        return TraceEdgeShape(
            TraceVersionRef(
                row.source_owner_module, row.source_object_type,
                row.source_object_id, row.source_version_id,
                "GLOBAL" if row.source_project_id is None else "PROJECT",
                row.source_project_id,
            ),
            TraceVersionRef(
                row.target_owner_module, row.target_object_type,
                row.target_object_id, row.target_version_id,
                "PROJECT", row.target_project_id,
            ),
            row.relation_type, row.scope, row.project_id,
        )
