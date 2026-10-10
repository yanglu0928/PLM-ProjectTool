"""Trace-owned replacement storage; source row and new edge share one transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.trace.application.supersede_link import TraceSupersedeState
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.create_repository import SqlAlchemyTraceCreateRepository
from plm_assistant.modules.trace.infrastructure.orm import TraceLinkRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Trace transaction is required")
    return session


class SqlAlchemyTraceSupersedeRepository(SqlAlchemyTraceCreateRepository):
    def lock(self, transaction: object, *, project_id: uuid.UUID,
             trace_link_id: uuid.UUID) -> TraceSupersedeState | None:
        row = _session(transaction).execute(
            select(TraceLinkRow).where(
                TraceLinkRow.scope == "PROJECT",
                TraceLinkRow.project_id == project_id,
                TraceLinkRow.trace_link_id == trace_link_id,
            ).with_for_update().execution_options(populate_existing=True),
        ).scalar_one_or_none()
        if row is None:
            return None
        source = TraceVersionRef(
            row.source_owner_module, row.source_object_type,
            row.source_object_id, row.source_version_id,
            "PROJECT" if row.source_project_id is not None else "GLOBAL",
            row.source_project_id,
        )
        target = TraceVersionRef(
            row.target_owner_module, row.target_object_type,
            row.target_object_id, row.target_version_id,
            "PROJECT" if row.target_project_id is not None else "GLOBAL",
            row.target_project_id,
        )
        edge = TraceEdgeShape(source, target, row.relation_type)
        if edge.project_id != project_id:
            raise RuntimeError("Trace relationship shape changed")
        return TraceSupersedeState(
            row.trace_link_id, project_id, row.link_state,
            row.lock_version, edge, row.superseded_by_ref,
        )

    def supersede(self, transaction: object, *, project_id: uuid.UUID,
                  trace_link_id: uuid.UUID, expected_version: int,
                  replacement_id: uuid.UUID) -> int:
        version = _session(transaction).execute(
            update(TraceLinkRow).where(
                TraceLinkRow.scope == "PROJECT",
                TraceLinkRow.project_id == project_id,
                TraceLinkRow.trace_link_id == trace_link_id,
                TraceLinkRow.link_state == "ACTIVE",
                TraceLinkRow.lock_version == expected_version,
            ).values(link_state="SUPERSEDED",
                     superseded_by_ref=replacement_id).returning(TraceLinkRow.lock_version),
        ).scalar_one_or_none()
        if version is None:
            raise RuntimeError("locked Trace replacement transition was lost")
        return version
