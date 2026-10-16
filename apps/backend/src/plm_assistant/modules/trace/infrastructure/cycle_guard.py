"""Transaction-scoped cycle guard for controlled TraceLink relation families."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape


_CONTROLLED = frozenset({"DERIVED_FROM", "SUPERSEDES"})
_REACHABLE = text("""
    WITH RECURSIVE walk(owner_module, object_type, object_id, version_id) AS (
        SELECT CAST(:target_owner AS text), CAST(:target_type AS text),
               CAST(:target_object AS uuid), CAST(:target_version AS uuid)
        UNION
        SELECT link.target_owner_module, link.target_object_type,
               link.target_object_id, link.target_version_id
          FROM walk AS node
          JOIN plm.trc_links AS link
            ON link.source_owner_module=node.owner_module
           AND link.source_object_type=node.object_type
           AND link.source_object_id=node.object_id
           AND link.source_version_id=node.version_id
         WHERE link.link_state='ACTIVE'
           AND link.relation_type IN ('DERIVED_FROM','SUPERSEDES')
           AND link.scope=:scope
           AND link.project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
    )
    SELECT EXISTS (
        SELECT 1 FROM walk
         WHERE owner_module=:source_owner
           AND object_type=:source_type
           AND object_id=CAST(:source_object AS uuid)
           AND version_id=CAST(:source_version AS uuid)
    )
""")


class TraceCycleError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("TraceLink cycle rejected")


class SqlAlchemyTraceCycleGuard:
    def assert_acyclic(self, transaction: object, edge: TraceEdgeShape) -> None:
        if type(edge) is not TraceEdgeShape:
            raise ValueError("validated Trace edge required")
        if edge.relation_type not in _CONTROLLED:
            return
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Trace transaction required")
        lock_key = f"trace-cycle:{edge.scope}:{edge.project_id or 'global'}"
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": lock_key},
        )
        reachable = session.execute(_REACHABLE, {
            "target_owner": edge.target.owner_module,
            "target_type": edge.target.object_type,
            "target_object": edge.target.object_id,
            "target_version": edge.target.version_id,
            "source_owner": edge.source.owner_module,
            "source_type": edge.source.object_type,
            "source_object": edge.source.object_id,
            "source_version": edge.source.version_id,
            "scope": edge.scope,
            "project_id": edge.project_id,
        }).scalar_one()
        if reachable is True:
            raise TraceCycleError()
