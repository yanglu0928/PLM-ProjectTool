"""Read immutable membership only. Trusted Owner must authorize/root/seal-bind first."""
from uuid import UUID
from sqlalchemy import select
from ..application.render_export import AuditExportRenderItem,AuditExportRenderError
from ..application.queries.audit_query import AuditEventView
from .audit_read_repository import _session
from .audit_orm import AuditEventRow
from .export_orm import members

_FIELDS=("audit_event_id","occurred_at","trace_id","event_scope","target_project_id","actor_type","actor_id",
    "original_actor_id","action","outcome","target_owner_module","target_object_type","target_object_id",
    "target_version_id","reason_code","before_state","after_state")


class SqlAlchemyAuditExportRenderSource:
    def iter_events(self,transaction,*,export_id):
        if type(export_id) is not UUID or not export_id.int:raise AuditExportRenderError()
        statement=select(members.c.position,*(getattr(AuditEventRow,field) for field in _FIELDS)).join(
            AuditEventRow,members.c.event_id==AuditEventRow.audit_event_id).where(members.c.export_id==export_id).order_by(members.c.position)
        result=_session(transaction).execute(statement.execution_options(yield_per=128)).mappings()
        try:
            for row in result:
                yield AuditExportRenderItem(row["position"],AuditEventView(**{field:row[field] for field in _FIELDS}))
        finally:result.close()
