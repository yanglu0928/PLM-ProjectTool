"""Audit-owned exact append-only event proof, no foreign private table reads."""
from sqlalchemy import select
from .audit_read_repository import _session
from .audit_orm import AuditEventRow
from ..application.upload_commit_source import UploadCommitAuditQuery,UploadCommitAuditSourceError as Error

class SqlAlchemyUploadCommitAuditSources:
    def verify(self,tx,*,query):
        if type(query) is not UploadCommitAuditQuery:raise Error('AUDIT_UNAVAILABLE')
        query.__post_init__()
        rows=_session(tx).scalars(select(AuditEventRow).where(AuditEventRow.action=='DOCUMENT_UPLOAD_COMMIT',
            AuditEventRow.target_version_id==query.document_version_id).limit(2)).all()
        if len(rows)!=1:raise Error('AUDIT_UNAVAILABLE')
        r=rows[0]
        if (r.trace_id,r.event_scope,r.target_project_id,r.actor_type,r.actor_id,r.original_actor_id,r.actor_hint_digest,
            r.outcome,r.target_owner_module,r.target_object_type,r.target_object_id,r.reason_code,r.before_state,r.after_state)!= (
            query.trace_id,'PROJECT' if query.scope=='PROJECT' else 'DEPLOYMENT',query.project_id,'USER',query.actor_id,None,None,
            'SUCCESS','document','DOC-02',query.document_id,None,None,'AVAILABLE') or r.occurred_at<query.version_created_at:
            raise Error('AUDIT_UNAVAILABLE')
        return r.audit_event_id
