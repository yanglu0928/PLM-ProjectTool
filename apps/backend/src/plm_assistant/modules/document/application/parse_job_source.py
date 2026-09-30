"""Document provenance facts; callers still need current authority/Jobs binding."""
from dataclasses import dataclass,field
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

@dataclass(frozen=True,slots=True)
class DocumentParseInputSource:
    """Private source metadata; not an authorization token or verified byte stream."""
    committed:CommittedParseDocumentSource
    storage_locator:str=field(repr=False)
    content_sha256:bytes=field(repr=False)
    size_bytes:int
    detected_mime:str

    def __post_init__(self):
        if type(self.committed) is not CommittedParseDocumentSource:
            raise DocumentParseSourceError()
        self.committed.__post_init__()
        if (type(self.storage_locator) is not str or not 1<=len(self.storage_locator)<=1024
            or self.storage_locator.startswith('/') or '..' in self.storage_locator
            or self.storage_locator.startswith('temp/')
            or ':' in self.storage_locator or '\\' in self.storage_locator
            or type(self.content_sha256) is not bytes or len(self.content_sha256)!=32
            or type(self.size_bytes) is not int or not 0<=self.size_bytes<=100_000_000
            or type(self.detected_mime) is not str or not 1<=len(self.detected_mime)<=255
            or self.detected_mime!=self.detected_mime.strip()
            or any(ord(char)<33 or ord(char)>126 for char in self.detected_mime)):
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

    def read_input(self,tx,*,request):
        """Require the existing committed-source/Audit proof before private bytes metadata."""
        source=self.read(tx,request=request)
        try:
            result=self._repo.get_input(tx,request=request)
            if type(result) is not DocumentParseInputSource or result.committed!=source:
                raise DocumentParseSourceError()
            result.__post_init__()
            return result
        except DocumentParseSourceError:raise
        except Exception:raise DocumentParseSourceError() from None
