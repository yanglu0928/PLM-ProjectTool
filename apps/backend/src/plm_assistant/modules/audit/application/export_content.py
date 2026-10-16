"""Current Session access to an actual published result; no HTTP or static paths."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID
from .authorized_read import AuthorizedAuditReadError
from .export_result import AuditExportResult
from .render_plan import AuditRenderPlan
from .submit_export import AcceptedAuditExport
from .public import AuditEventDraft
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate,AuditFileContent
from plm_assistant.modules.document.application.audit_export_metadata import AuditRegisteredFileRequest,AuditFileMetadata
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef


@dataclass(frozen=True,slots=True)
class AuditExportContentQuery:
    session_token: bytes=field(repr=False)
    project_id: UUID|None
    trace_id: UUID
    export_id: UUID

    def __post_init__(self):
        if (type(self.session_token) is not bytes or len(self.session_token)!=32
                or any(type(v) is not UUID or not v.int for v in (self.trace_id,self.export_id))
                or self.project_id is not None and (type(self.project_id) is not UUID or not self.project_id.int)):
            raise AuthorizedAuditReadError('VALIDATION_FAILED')


@dataclass(frozen=True,slots=True)
class AuthorizedAuditExportSource:
    """Checked binding metadata, NOT a reusable Session/download permission."""
    actor_id: UUID
    result: AuditExportResult
    content: AuditFileContent

    def __post_init__(self):
        if type(self.actor_id) is not UUID or not self.actor_id.int or type(self.result) is not AuditExportResult or type(self.content) is not AuditFileContent:
            raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        self.result.__post_init__();self.content.__post_init__()
        if (self.result.file_id,self.result.file_sha256,self.result.byte_count)!=(self.content.coordinate.file_id,self.content.sha256,self.content.size_bytes):
            raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')


class AuditExportContentReader:
    def __init__(self,*,unit_of_work,project_access,deployment_access,projects,license_guard,repository,results,plans,files,completion,audit,clock=None):
        if any(v is None for v in (unit_of_work,project_access,deployment_access,projects,license_guard,repository,results,plans,files,completion,audit)):
            raise ValueError('Content reader dependencies required')
        self._uow,self._project_access,self._deployment_access=unit_of_work,project_access,deployment_access
        self._projects,self._guard,self._repository=projects,license_guard,repository
        self._results,self._plans,self._files,self._completion,self._audit=results,plans,files,completion,audit
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def _authorize(self,tx,q):
        self._guard.require_valid(trace_id=q.trace_id)
        now=self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        actor=(self._deployment_access.authorized_admin if q.project_id is None else self._project_access.authenticated_user)(
            tx,session_token=q.session_token,now=now)
        if type(actor) is not UUID or not actor.int:raise AuthorizedAuditReadError('AUTH_ACCESS_DENIED')
        if q.project_id is not None:
            proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=q.project_id,operation='AUDIT_PROJECT_GET')
            if (type(proof) is not AuthorizedProjectAction or (proof.user_id,proof.project_id,proof.operation,proof.project_role)
                    !=(actor,q.project_id,'AUDIT_PROJECT_GET','PROJECT_MANAGER')):raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
        return actor

    def _source(self,tx,q):
        actor=self._authorize(tx,q)
        intent=self._repository.get_created(tx,export_id=q.export_id)
        if intent is None or (intent.spec.scope,intent.spec.project_id)!=('DEPLOYMENT' if q.project_id is None else 'PROJECT',q.project_id):
            raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
        intent.__post_init__()
        accepted=self._repository.get_accepted(tx,intent=intent)
        result=self._results.get(tx,export_id=q.export_id)
        if type(result) is not AuditExportResult:raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
        result.__post_init__()
        if result.export_id!=q.export_id:raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        plan=self._plans.get(tx,render_attempt_id=result.render_attempt_id)
        if (type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or type(plan) is not AuditRenderPlan
                or (plan.export_id,plan.job_id,plan.file_id)!=(q.export_id,accepted.job_id,result.file_id)):
            raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        accepted.__post_init__();plan.__post_init__()
        claim=self._completion.assert_succeeded(tx,request=AuditExportJobRequest(intent.export_id,intent.actor_id,
            intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version),
            refs=AuditExportJobRef(accepted.job_id,accepted.event_id),fencing_token=plan.fencing_token,worker_ref=plan.worker_ref)
        if claim.attempt_no!=plan.attempt_no:raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        coordinate=AuditFileCoordinate(result.file_id,intent.spec.scope,intent.spec.project_id)
        metadata=self._files.read_registered(tx,request=AuditRegisteredFileRequest(intent.export_id,intent.actor_id,intent.trace_id,coordinate))
        expected=AuditFileContent(coordinate,result.file_sha256,result.byte_count)
        if (type(metadata) is not AuditFileMetadata or metadata.state!='AVAILABLE' or metadata.content!=expected):
            raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
        metadata.__post_init__()
        if (metadata.export_id,metadata.actor_id,metadata.registration_trace_id)!=(intent.export_id,intent.actor_id,intent.trace_id):
            raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        if self._authorize(tx,q)!=actor:raise AuthorizedAuditReadError('AUTH_ACCESS_DENIED')
        return AuthorizedAuditExportSource(actor,result,expected)

    def _call(self,q,operation):
        if type(q) is not AuditExportContentQuery:raise AuthorizedAuditReadError('VALIDATION_FAILED')
        q.__post_init__()
        try:
            with self._uow() as tx:return operation(tx,q)
        except AuthorizedAuditReadError:raise
        except ProjectAuthorizationError:raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND') from None
        except RuntimeLicenseError:raise AuthorizedAuditReadError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE') from None

    def get_source(self,q):return self._call(q,self._source)

    def record_content_failure(self,q,source):
        def record(tx,query):
            current=self._source(tx,query)
            if current!=source:raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
            self._audit.append(tx,AuditEventDraft(trace_id=query.trace_id,event_scope=current.content.coordinate.scope,
                target_project_id=query.project_id,actor_type='USER',actor_id=current.actor_id,original_actor_id=None,
                actor_hint_digest=None,action='AUDIT_EXPORT_DOWNLOAD_CONTENT_FAILED',outcome='FAILED',
                target_owner_module='document',target_object_type='DOC-03',target_object_id=current.result.file_id,
                reason_code='FILE_CONTENT_UNAVAILABLE'))
            tx.commit()
        return self._call(q,record)


@dataclass(slots=True)
class VerifiedAuditExportDownload:
    export_id: UUID
    size_bytes: int
    content_sha256: bytes=field(repr=False)
    stream: object=field(repr=False)
    detected_mime: str='application/x-ndjson'
    def close(self):self.stream.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class PrepareAuditExportContent:
    def __init__(self,*,reader,storage):
        if reader is None or storage is None:raise ValueError('Reader/storage required')
        self._reader,self._storage=reader,storage

    def _source(self,q):
        if type(q) is not AuditExportContentQuery:raise AuthorizedAuditReadError('VALIDATION_FAILED')
        q.__post_init__()
        value=self._reader.get_source(q)
        if type(value) is not AuthorizedAuditExportSource:raise AuthorizedAuditReadError('AUDIT_UNAVAILABLE')
        value.__post_init__()
        if (value.result.export_id,value.content.coordinate.scope,value.content.coordinate.project_id)!=(
                q.export_id,'DEPLOYMENT' if q.project_id is None else 'PROJECT',q.project_id):
            raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
        return value

    def prepare(self,q):
        source=self._source(q)
        try:snapshot=self._storage.open_snapshot(source.content)
        except Exception:
            self._reader.record_content_failure(q,source)
            raise AuthorizedAuditReadError('AUDIT_EXPORT_CONTENT_UNAVAILABLE') from None
        try:
            if self._source(q)!=source:raise AuthorizedAuditReadError('RESOURCE_NOT_FOUND')
            return VerifiedAuditExportDownload(q.export_id,source.content.size_bytes,source.content.sha256,snapshot)
        except Exception:
            snapshot.close();raise
