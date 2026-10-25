"""Read-lock current project IMPLEMENTS edges for a fixed Solution version."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef

from .create_repository import _session
from .orm import TraceLinkRow


class SqlAlchemyTraceImplementsRepository:
    def active_for_target(self, transaction: object, *,
                          project_id: uuid.UUID,
                          target: TraceVersionRef,
                          limit: int) -> tuple[TraceAdjacency, ...]:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(target) is not TraceVersionRef
                or target.owner_module != "solution"
                or target.object_type not in ("SOL-05", "SOL-06")
                or (target.scope, target.project_id) != ("PROJECT", project_id)
                or type(limit) is not int or limit != 501):
            raise ValueError("bounded fixed Solution version query required")
        rows = _session(transaction).execute(select(TraceLinkRow).where(
            TraceLinkRow.scope == "PROJECT",
            TraceLinkRow.project_id == project_id,
            TraceLinkRow.link_state == "ACTIVE",
            TraceLinkRow.relation_type == "IMPLEMENTS",
            TraceLinkRow.target_owner_module == "solution",
            TraceLinkRow.target_object_type == target.object_type,
            TraceLinkRow.target_object_id == target.object_id,
            TraceLinkRow.target_version_id == target.version_id,
            TraceLinkRow.target_project_id == project_id,
        ).order_by(TraceLinkRow.trace_link_id).limit(limit).with_for_update(
            read=True, of=TraceLinkRow,
        )).scalars().all()
        return tuple(TraceAdjacency(
            row.trace_link_id,
            TraceEdgeShape(
                TraceVersionRef(
                    row.source_owner_module, row.source_object_type,
                    row.source_object_id, row.source_version_id,
                    "PROJECT" if row.source_project_id is not None else "GLOBAL",
                    row.source_project_id,
                ),
                TraceVersionRef(
                    row.target_owner_module, row.target_object_type,
                    row.target_object_id, row.target_version_id,
                    "PROJECT", row.target_project_id,
                ),
                row.relation_type, row.scope, row.project_id,
            ),
        ) for row in rows)
