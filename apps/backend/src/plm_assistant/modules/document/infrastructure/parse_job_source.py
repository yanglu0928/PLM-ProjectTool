"""Document-owned upload/version/file/ordinal0 facts, no Jobs/Audit SQL."""
from sqlalchemy import select
from .read_repository import _session
from .orm import DocumentRow,UploadIntentRow,FileObjectRow,DocumentVersionRow,DocumentVersionSourceRefRow
from ..application.parse_job_source import CommittedParseDocumentSource,DocumentParseSourceError as Error
from plm_assistant.modules.jobs.application.parse_enqueue import validate_parse_read_request

class SqlAlchemyDocumentParseSources:
    def get(self,tx,*,request):
        validate_parse_read_request(request);session=_session(tx)
        def row(kind,id_column,value):return session.scalar(select(kind).where(id_column==value).with_for_update(read=True,of=kind).execution_options(populate_existing=True))
        doc=row(DocumentRow,DocumentRow.document_id,request.document_id)
        if doc is None or (doc.scope,doc.project_id)!=(request.scope,request.project_id) or doc.document_state not in ('ACTIVE','ARCHIVED'):
            return None
        intent=row(UploadIntentRow,UploadIntentRow.upload_id,request.upload_id)
        if intent is None:return None
        if (intent.state,intent.purpose_code,intent.scope,intent.project_id,intent.actor_id,intent.committed_document_id,intent.document_version_id)!= (
            'COMMITTED','SOURCE_UPLOAD',request.scope,request.project_id,request.actor_id,request.document_id,request.document_version_id):raise Error()
        file=row(FileObjectRow,FileObjectRow.file_object_id,intent.file_object_id)
        version=row(DocumentVersionRow,DocumentVersionRow.document_version_id,request.document_version_id)
        if file is None or version is None:raise Error()
        if version.availability_state!='AVAILABLE' or file.file_state!='AVAILABLE':return None
        if (version.document_id,version.scope,version.project_id,version.version_no,version.file_object_id,version.created_by,
            version.availability_state,version.source_metadata)!= (request.document_id,request.scope,request.project_id,request.version_no,
            intent.file_object_id,request.actor_id,'AVAILABLE',{'source_kind':'UPLOAD'}):raise Error()
        if (file.scope,file.project_id,file.usage_kind,file.owner_object_id,file.storage_class,file.file_state,file.created_by,
            file.sha256,file.size_bytes,file.detected_mime)!= (request.scope,request.project_id,'DOCUMENT',None,'PERSISTENT','AVAILABLE',request.actor_id,
            version.content_sha256,version.size_bytes,version.detected_mime):raise Error()
        if version.integrity_checked_at is None or file.available_at is None or file.available_at>version.created_at or intent.created_at>version.created_at:
            raise Error()
        source=session.scalar(select(DocumentVersionSourceRefRow).where(DocumentVersionSourceRefRow.document_version_id==version.document_version_id,DocumentVersionSourceRefRow.ordinal==0))
        if source is None or (source.source_kind,source.source_owner_module,source.source_object_type,source.source_object_id,source.source_version_id)!=('UPLOAD',None,None,None,None):raise Error()
        return CommittedParseDocumentSource(request,file.file_object_id,version.created_at)
