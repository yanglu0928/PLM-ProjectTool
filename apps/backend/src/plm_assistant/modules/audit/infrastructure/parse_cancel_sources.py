"""Audit-owned Parser cancellation event receipt and first request proof."""

from sqlalchemy import select

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.audit.infrastructure.audit_read_repository import _session


class ParseCancelAuditSourceError(RuntimeError):
    pass


class SqlAlchemyParseCancelAuditSources:
    def verified_recovery(self, tx, *, job_id, project_id, document_version_id,
                          trace_id, actor_id, original_actor_id, requested_at, completed_at):
        rows = _session(tx).scalars(select(AuditEventRow).where(
            AuditEventRow.action == "DOCUMENT_PARSE_CANCEL_RECOVERED",
            AuditEventRow.target_owner_module == "jobs",
            AuditEventRow.target_object_type == "JOB-01",
            AuditEventRow.target_object_id == job_id).limit(2)).all()
        if len(rows) != 1:
            raise ParseCancelAuditSourceError()
        event = rows[0]
        if (event.event_scope != "PROJECT" or event.target_project_id != project_id
                or event.trace_id != trace_id or event.actor_type != "SYSTEM"
                or event.actor_id != actor_id or event.original_actor_id != original_actor_id
                or event.actor_hint_digest is not None or event.outcome != "SUCCESS"
                or event.target_version_id != document_version_id
                or event.before_state != "CANCEL_REQUESTED"
                or event.after_state != "CANCELLED" or event.reason_code != "LEASE_EXPIRED"
                or event.occurred_at < requested_at or event.occurred_at > completed_at):
            raise ParseCancelAuditSourceError()
        return event.audit_event_id

    @staticmethod
    def _bound(event, *, job_id, project_id):
        if (event is None or event.event_scope != "PROJECT" or event.target_project_id != project_id
                or event.actor_type != "USER" or event.actor_id is None
                or event.original_actor_id is not None or event.actor_hint_digest is not None
                or event.outcome != "SUCCESS" or event.target_owner_module != "jobs"
                or event.target_object_type != "JOB-01" or event.target_object_id != job_id
                or event.target_version_id is not None or event.reason_code != "USER_REQUESTED"):
            raise ParseCancelAuditSourceError()

    def receipt(self, tx, *, job_id, project_id, actor_id, event_id):
        event = _session(tx).scalar(select(AuditEventRow).where(AuditEventRow.audit_event_id == event_id))
        self._bound(event, job_id=job_id, project_id=project_id)
        if event.actor_id != actor_id:
            raise ParseCancelAuditSourceError()
        changed = event.action == "DOCUMENT_PARSE_CANCEL_REQUESTED"
        if changed:
            expected = {"PENDING": "CANCELLED", "RETRY_WAIT": "CANCELLED",
                        "RUNNING": "CANCEL_REQUESTED"}.get(event.before_state)
            if expected is None or event.after_state != expected:
                raise ParseCancelAuditSourceError()
        elif (event.action != "DOCUMENT_PARSE_CANCEL_CHECKED"
              or event.before_state != event.after_state
              or event.after_state not in {"CANCEL_REQUESTED", "CANCELLED", "SUCCEEDED", "FAILED"}):
            raise ParseCancelAuditSourceError()
        return event.after_state, changed

    def first_request(self, tx, *, job_id, project_id, requested_by, requested_at):
        rows = _session(tx).scalars(select(AuditEventRow).where(
            AuditEventRow.action == "DOCUMENT_PARSE_CANCEL_REQUESTED",
            AuditEventRow.target_owner_module == "jobs",
            AuditEventRow.target_object_type == "JOB-01",
            AuditEventRow.target_object_id == job_id).limit(2)).all()
        if len(rows) != 1:
            raise ParseCancelAuditSourceError()
        event = rows[0]
        self._bound(event, job_id=job_id, project_id=project_id)
        if event.actor_id != requested_by or requested_at is None or event.occurred_at < requested_at:
            raise ParseCancelAuditSourceError()
        self.receipt(tx, job_id=job_id, project_id=project_id,
                     actor_id=requested_by, event_id=event.audit_event_id)
        return event.audit_event_id
