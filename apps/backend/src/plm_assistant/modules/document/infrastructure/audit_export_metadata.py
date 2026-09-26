"""Document-owned exact file metadata/events; never touches Audit/Job private tables."""
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from .orm import FileObjectRow, FileStateEventRow
from .audit_export_storage import _locators
from ..application.audit_export_metadata import (
    RegisterAuditFile, AuditFileMetadata, AuditFileMutation, AuditFileMetadataError,
)


def _session(transaction,request):
    if type(request) is not RegisterAuditFile:raise AuditFileMetadataError()
    request.__post_init__()
    try:session=transaction.session
    except (AttributeError,RuntimeError):raise AuditFileMetadataError() from None
    if not isinstance(session,Session) or not session.in_transaction():raise AuditFileMetadataError()
    return session


class SqlAlchemyAuditExportFileMetadata:
    def register_staged(self,transaction,*,request):
        session=_session(transaction,request)
        try:
            content=request.content;coordinate=content.coordinate
            _,final=_locators(coordinate)
            identity=session.execute(insert(FileObjectRow).values(
                file_object_id=coordinate.file_id,usage_kind="AUDIT_EXPORT",owner_object_id=request.export_id,
                scope=coordinate.scope,project_id=coordinate.project_id,storage_class="PERSISTENT",
                storage_locator=final,original_name_metadata="audit-export.jsonl",sha256=content.sha256,
                size_bytes=content.size_bytes,detected_mime="application/x-ndjson",file_state="STAGED",
                created_by=request.actor_id,
            ).on_conflict_do_nothing(index_elements=[FileObjectRow.file_object_id])
                .returning(FileObjectRow.file_object_id)).scalar_one_or_none()
            if identity is not None:
                session.add(FileStateEventRow(file_object_id=identity,from_state=None,to_state="STAGED",
                    reason_code="AUDIT_EXPORT_REGISTER",actor_user_id=request.actor_id,trace_id=request.trace_id))
                session.flush()
            row=self._row(session,request,lock=True)
            return AuditFileMutation(self._view(session,row,request),identity is not None)
        except AuditFileMetadataError:raise
        except Exception:raise AuditFileMetadataError() from None

    def get(self,transaction,*,request):
        session=_session(transaction,request)
        try:return self._view(session,self._row(session,request,lock=False),request)
        except AuditFileMetadataError:raise
        except Exception:raise AuditFileMetadataError() from None

    def mark_available(self,transaction,*,request,expected_version):
        session=_session(transaction,request)
        if type(expected_version) is not int or expected_version!=0:raise AuditFileMetadataError("CONFLICT_VERSION")
        try:
            row=self._row(session,request,lock=True)
            current=self._view(session,row,request)
            if current.state=="AVAILABLE":return AuditFileMutation(current,False)
            if current.state!="STAGED":raise AuditFileMetadataError("CONFLICT_STATE")
            if current.lock_version!=expected_version:raise AuditFileMetadataError("CONFLICT_VERSION")
            now=session.scalar(select(func.clock_timestamp()))
            row.file_state="AVAILABLE";row.lock_version=1;row.available_at=now
            row.updated_at=now;row.updated_by=request.actor_id
            session.add(FileStateEventRow(file_object_id=row.file_object_id,from_state="STAGED",to_state="AVAILABLE",
                reason_code="AUDIT_EXPORT_PUBLISH",actor_user_id=request.actor_id,trace_id=request.trace_id,created_at=now))
            session.flush()
            return AuditFileMutation(self._view(session,row,request),True)
        except AuditFileMetadataError:raise
        except Exception:raise AuditFileMetadataError() from None

    @staticmethod
    def _row(session,request,*,lock):
        query=select(FileObjectRow).where(FileObjectRow.file_object_id==request.content.coordinate.file_id)
        return session.execute(query.with_for_update(read=not lock)).scalar_one_or_none()

    @staticmethod
    def _view(session,row,request):
        content=request.content;coordinate=content.coordinate
        if row is None:raise AuditFileMetadataError("RESOURCE_NOT_FOUND")
        _,final=_locators(coordinate)
        if ((row.usage_kind,row.owner_object_id,row.scope,row.project_id,row.created_by,row.storage_class,
             row.storage_locator,row.original_name_metadata,row.sha256,row.size_bytes,row.detected_mime)
            !=("AUDIT_EXPORT",request.export_id,coordinate.scope,coordinate.project_id,request.actor_id,"PERSISTENT",
               final,"audit-export.jsonl",content.sha256,content.size_bytes,"application/x-ndjson")):
            raise AuditFileMetadataError()
        events=list(session.scalars(select(FileStateEventRow).where(FileStateEventRow.file_object_id==row.file_object_id)))
        created=[e for e in events if e.from_state is None and e.to_state=="STAGED" and e.reason_code=="AUDIT_EXPORT_REGISTER"]
        available=[e for e in events if e.from_state=="STAGED" and e.to_state=="AVAILABLE" and e.reason_code=="AUDIT_EXPORT_PUBLISH"]
        if (len(created)!=1 or created[0].actor_user_id!=request.actor_id or created[0].created_at<row.created_at
                or not created[0].trace_id.int):raise AuditFileMetadataError()
        if row.file_state=="STAGED":
            if row.lock_version!=0 or row.available_at is not None or available:raise AuditFileMetadataError()
        elif row.file_state in ("AVAILABLE","RESTRICTED"):
            if (row.lock_version!=(1 if row.file_state=="AVAILABLE" else 2) or len(available)!=1
                    or available[0].actor_user_id!=request.actor_id or row.available_at!=available[0].created_at
                    or row.available_at<created[0].created_at or not available[0].trace_id.int):raise AuditFileMetadataError()
        else:raise AuditFileMetadataError("CONFLICT_STATE")
        return AuditFileMetadata(content,request.export_id,request.actor_id,created[0].trace_id,created[0].file_state_event_id,
            row.file_state,row.lock_version,row.created_at,row.available_at,available[0].file_state_event_id if available else None)
