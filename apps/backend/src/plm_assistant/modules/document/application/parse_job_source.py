"""Document provenance facts; callers still need current authority/Jobs binding."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobRequest,validate_parse_read_request
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditQuery

class DocumentParseSourceError(RuntimeError):
    def __init__(self,code='DOCUMENT_UNAVAILABLE'):self.code=code;super().__init__(code)

@dataclass(frozen=True,slots=True)
class CommittedParseDocumentSource:
    request:ParseJobRequest
    file_object_id:UUID
    version_created_at:datetime
    def __post_init__(self):
        try:validate_parse_read_request(self.request)
        except Exception:raise DocumentParseSourceError() from None
        if (type(self.file_object_id) is not UUID or not self.file_object_id.int
            or type(self.version_created_at) is not datetime or self.version_created_at.tzinfo is None or self.version_created_at.utcoffset() is None):
            raise DocumentParseSourceError()

class DocumentParseSourceReader:
    def __init__(self,*,repository,audit_sources):
        if repository is None or audit_sources is None:raise ValueError('Actual Document/Audit source Ports required')
        self._repo,self._audit=repository,audit_sources
    def read(self,tx,*,request):
        try:
            validate_parse_read_request(request)
            source=self._repo.get(tx,request=request)
            if source is None:raise DocumentParseSourceError('RESOURCE_NOT_FOUND')
            if type(source) is not CommittedParseDocumentSource or source.request!=request:raise DocumentParseSourceError()
            source.__post_init__()
            event=self._audit.verify(tx,query=UploadCommitAuditQuery(request.document_id,request.document_version_id,request.actor_id,
                request.trace_id,request.scope,request.project_id,source.version_created_at))
            if type(event) is not UUID or not event.int:raise DocumentParseSourceError()
            return source
        except DocumentParseSourceError:raise
        except Exception:raise DocumentParseSourceError() from None
