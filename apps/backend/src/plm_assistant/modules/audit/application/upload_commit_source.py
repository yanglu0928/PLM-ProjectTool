"""Readonly original upload Audit proof; not authorization or Document lookup."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

class UploadCommitAuditSourceError(RuntimeError):pass

@dataclass(frozen=True,slots=True)
class UploadCommitAuditQuery:
    document_id:UUID
    document_version_id:UUID
    actor_id:UUID
    trace_id:UUID
    scope:str
    project_id:UUID|None
    version_created_at:datetime
    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.document_id,self.document_version_id,self.actor_id,self.trace_id))
            or type(self.scope) is not str or self.scope not in ('GLOBAL','PROJECT')
            or self.scope=='GLOBAL' and self.project_id is not None
            or self.scope=='PROJECT' and (type(self.project_id) is not UUID or not self.project_id.int)
            or type(self.version_created_at) is not datetime or self.version_created_at.tzinfo is None or self.version_created_at.utcoffset() is None):
            raise UploadCommitAuditSourceError('AUDIT_UNAVAILABLE')

class UploadCommitAuditSources:
    def __init__(self,*,repository):
        if repository is None:raise ValueError('Actual Audit source repository required')
        self._repo=repository
    def verify(self,tx,*,query):
        if type(query) is not UploadCommitAuditQuery:raise UploadCommitAuditSourceError('AUDIT_UNAVAILABLE')
        query.__post_init__()
        try:
            value=self._repo.verify(tx,query=query)
            if type(value) is not UUID or not value.int:raise UploadCommitAuditSourceError('AUDIT_UNAVAILABLE')
            return value
        except Exception:raise UploadCommitAuditSourceError('AUDIT_UNAVAILABLE') from None
