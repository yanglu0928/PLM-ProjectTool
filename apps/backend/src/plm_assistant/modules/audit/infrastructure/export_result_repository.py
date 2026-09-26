"""Own-source full reread; caller supplies current authority/lease/file facts/UOW."""
from datetime import timezone
import hashlib
from uuid import UUID
from sqlalchemy import insert,select
from ..application.export_result import (
    AuditExportResult,AuditExportResultError,AuditExportResultMutation,RecordAuditExportResult,
)
from ..application.export_contract import AuditExportAuthorityRequest
from ..application.render_export import build_audit_export_manifest,MANIFEST_VERSION
from ..application.render_plan import AuditRenderPlan
from .audit_read_repository import _session
from .audit_orm import AuditEventRow
from .capture_repository import SqlAlchemyAuditCaptureRepository
from .export_submit_repository import SqlAlchemyAuditExportSubmitRepository
from .export_orm import results,render_attempts


class SqlAlchemyAuditExportResults:
    def record(self,tx,*,request):
        try:return self._record(tx,request)
        except AuditExportResultError:raise
        except Exception:raise AuditExportResultError() from None

    def get(self,tx,*,export_id):
        try:
            if type(export_id) is not UUID or not export_id.int:raise AuditExportResultError()
            session=_session(tx)
            intent=SqlAlchemyAuditExportSubmitRepository().get_created(tx,export_id=export_id)
            if intent is None:return None
            row=session.execute(select(results).where(results.c.export_id==export_id).with_for_update()).mappings().one_or_none()
            if row is None:return None  # Never manufacture result from a plan or files.
            return self._view(tx,row)
        except AuditExportResultError:raise
        except Exception:raise AuditExportResultError() from None

    @staticmethod
    def _source(tx,attempt_id):
        session=_session(tx)
        row=session.execute(select(render_attempts).where(render_attempts.c.render_attempt_id==attempt_id)).mappings().one_or_none()
        if row is None:raise AuditExportResultError()
        source=dict(row);source['created_at']=source['created_at'].astimezone(timezone.utc)
        plan=AuditRenderPlan(**source)
        repo=SqlAlchemyAuditExportSubmitRepository()
        intent=repo.get_created(tx,export_id=plan.export_id)
        if intent is None:raise AuditExportResultError()
        accepted=repo.get_accepted(tx,intent=intent)
        if accepted is None or accepted.job_id!=plan.job_id:raise AuditExportResultError()
        capture=SqlAlchemyAuditCaptureRepository().read_capture(tx,request=AuditExportAuthorityRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,'PUBLISH'))
        if (capture is None or (plan.member_count,plan.membership_hash,plan.membership_version)
                !=(capture.member_count,capture.membership_hash,capture.membership_version)
                or plan.created_at<capture.captured_at or plan.created_at<accepted.accepted_at):raise AuditExportResultError()
        return intent,capture,plan

    def _view(self,tx,row):
        values=dict(row);values['published_at']=values['published_at'].astimezone(timezone.utc)
        result=AuditExportResult(**values)
        intent,capture,plan=self._source(tx,result.render_attempt_id)
        if (result.export_id,result.file_id)!=(intent.export_id,plan.file_id) or result.published_at<plan.created_at:raise AuditExportResultError()
        expected=build_audit_export_manifest(intent,capture,file_sha256=result.file_sha256.hex(),byte_count=result.byte_count)
        if result.manifest_bytes!=expected:raise AuditExportResultError()
        fields=('audit_event_id','occurred_at','trace_id','event_scope','target_project_id','actor_type','actor_id','original_actor_id',
            'action','outcome','target_owner_module','target_object_type','target_object_id','target_version_id','reason_code','before_state','after_state')
        audit=_session(tx).execute(select(*(getattr(AuditEventRow,f) for f in fields)).where(AuditEventRow.audit_event_id==result.publish_audit_event_id)).mappings().one_or_none()
        if (audit is None or audit['actor_id'] is None or not audit['actor_id'].int
                or tuple(audit[f] for f in fields[2:])!=(intent.trace_id,intent.spec.scope,intent.spec.project_id,'SYSTEM',audit['actor_id'],intent.actor_id,
                    'AUDIT_EXPORT_PUBLISHED','SUCCESS','jobs','JOB-01',plan.job_id,None,intent.spec.purpose,'RUNNING','SUCCEEDED')
                or not plan.created_at<=audit['occurred_at']<=result.published_at):raise AuditExportResultError()
        return result

    def _record(self,tx,request):
        if type(request) is not RecordAuditExportResult:raise AuditExportResultError()
        request.__post_init__()
        intent,capture,plan=self._source(tx,request.plan.render_attempt_id)
        if plan!=request.plan:raise AuditExportResultError()
        r=request.rendered
        if r.manifest_bytes!=build_audit_export_manifest(intent,capture,file_sha256=r.file_sha256,byte_count=r.byte_count):raise AuditExportResultError()
        values=dict(export_id=plan.export_id,render_attempt_id=plan.render_attempt_id,file_id=plan.file_id,
            file_sha256=bytes.fromhex(r.file_sha256),byte_count=r.byte_count,mime_type='application/x-ndjson',
            manifest_version=MANIFEST_VERSION,manifest_bytes=r.manifest_bytes,manifest_sha256=hashlib.sha256(r.manifest_bytes).digest(),
            publish_audit_event_id=request.publish_audit_event_id)
        existing=self.get(tx,export_id=plan.export_id)
        if existing is not None:
            if any(getattr(existing,k)!=v for k,v in values.items()):raise AuditExportResultError()
            return AuditExportResultMutation(existing,False)
        _session(tx).execute(insert(results).values(**values))
        result=self.get(tx,export_id=plan.export_id)
        if result is None:raise AuditExportResultError()
        return AuditExportResultMutation(result,True)
