"""Current-authority paged DB reads, physical private rendering outside EVERY UOW."""
from dataclasses import dataclass
from uuid import UUID
from .render_plan import AuditExportWorkerRenderPlan,AuditRenderPlan
from .worker_capture import AuditExportWorkerError
from .render_export import (
    AuditExportRenderer,RenderedAuditExport,AuditExportRenderItem,AuditExportRenderPagePort,
    build_audit_export_manifest,AuditExportRenderError,
)
from .submit_export import AuditExportIntent
from .capture_contract import CapturedAuditExport
from plm_assistant.modules.document.application.audit_export_storage import (
    AuditFileCoordinate,AuditFileContent,AuditExportFileStoragePort,AuditFileStorageError,
)

PAGE_SIZE=128


@dataclass(frozen=True,slots=True)
class AuditRenderContext:
    intent: AuditExportIntent
    capture: CapturedAuditExport
    plan: AuditRenderPlan

    def __post_init__(self):
        if type(self.plan) is not AuditRenderPlan:raise AuditExportWorkerError()
        self.plan.__post_init__()
        AuditExportRenderer._bound(self.intent,self.capture)
        if ((self.plan.export_id,self.plan.member_count,self.plan.membership_hash,self.plan.membership_version)
                !=(self.intent.export_id,self.capture.member_count,self.capture.membership_hash,self.capture.membership_version)
                or self.plan.created_at<self.capture.captured_at):raise AuditExportWorkerError()


@dataclass(frozen=True,slots=True)
class StagedAuditExport:
    context: AuditRenderContext
    rendered: RenderedAuditExport
    content: AuditFileContent

    def __post_init__(self):
        if type(self.context) is not AuditRenderContext or type(self.rendered) is not RenderedAuditExport or type(self.content) is not AuditFileContent:
            raise AuditExportWorkerError()
        self.context.__post_init__();self.content.__post_init__()
        r,c=self.rendered,self.context
        if (type(r.export_id) is not UUID or not r.export_id.int
                or (r.export_id,r.member_count)!=(c.intent.export_id,c.capture.member_count)
                or type(r.member_count) is not int
                or (self.content.coordinate.file_id,self.content.coordinate.scope,self.content.coordinate.project_id)
                    !=(c.plan.file_id,c.intent.spec.scope,c.intent.spec.project_id)
                or self.content.sha256.hex()!=r.file_sha256 or self.content.size_bytes!=r.byte_count
                or type(r.manifest_bytes) is not bytes
                or r.manifest_bytes!=build_audit_export_manifest(c.intent,c.capture,file_sha256=r.file_sha256,byte_count=r.byte_count)):
            raise AuditExportWorkerError()


class AuditExportWorkerRender(AuditExportWorkerRenderPlan):
    def __init__(self,*,source:AuditExportRenderPagePort,storage:AuditExportFileStoragePort,**dependencies):
        if source is None or storage is None:raise ValueError('Render source/storage required')
        super().__init__(**dependencies)
        self._source,self._storage=source,storage

    def _prepare(self,c):
        with self._uow() as tx:
            intent,request,claim,capture,plan=self._prepared(tx,c)
            context=AuditRenderContext(intent,capture,plan)
            if self._authority.assert_current(tx,request=request) is not None:raise AuditExportWorkerError()
            if self._lease(tx,c,intent)!=claim:raise AuditExportWorkerError()
            tx.commit();return context

    def _stage(self,c,context,*,after=None):
        with self._uow() as tx:
            intent,request,claim=self._authorized(tx,c,'RENDER')
            if (intent!=context.intent or claim.attempt_no!=context.plan.attempt_no):raise AuditExportWorkerError()
            if after is None:
                capture=self._captures.read_capture(tx,request=request)
                self._result(capture,intent)
                if capture!=context.capture:raise AuditExportWorkerError()
                batch=None
            else:
                batch=self._source.read_page(tx,export_id=intent.export_id,after_position=after,page_size=PAGE_SIZE)
                expected=min(PAGE_SIZE,context.capture.member_count-after)
                if (type(batch) is not tuple or len(batch)!=expected
                        or any(type(item) is not AuditExportRenderItem or type(item.position) is not int
                            or item.position!=after+i for i,item in enumerate(batch,1))):raise AuditExportWorkerError()
            if self._authority.assert_current(tx,request=request) is not None:raise AuditExportWorkerError()
            if self._lease(tx,c,intent)!=claim:raise AuditExportWorkerError()
            tx.commit();return batch

    def render(self,command)->StagedAuditExport:
        """No whole-file retry/overwriting. Partial files remain private for a NEW generation."""
        context=self._run(command,self._prepare)  # ONLY this short DB stage may deadlock-retry.
        coordinate=AuditFileCoordinate(context.plan.file_id,context.intent.spec.scope,context.intent.spec.project_id)
        current_failure=[]
        def items():
            position=0
            while position<context.capture.member_count:
                try:batch=self._run(command,lambda c:self._stage(c,context,after=position))
                except AuditExportWorkerError as exc:current_failure.append(exc);raise
                for item in batch:yield item
                position+=len(batch)
        try:
            with self._storage.staging_sink(coordinate) as sink:
                rendered=AuditExportRenderer().render(intent=context.intent,capture=context.capture,items=items(),sink=sink)
            content=AuditFileContent(coordinate,bytes.fromhex(rendered.file_sha256),rendered.byte_count)
            proof=self._storage.verify_staged(content)  # Reopen/hash AFTER flush/fsync/close, no UOW.
            if type(proof) is not AuditFileContent or proof!=content:raise AuditExportWorkerError()
            self._run(command,lambda c:self._stage(c,context))
            return StagedAuditExport(context,rendered,proof)
        except Exception as exc:
            if current_failure:raise current_failure[0] from None
            if isinstance(exc,AuditExportWorkerError):raise
            if (isinstance(exc,AuditExportRenderError) and exc.code=='AUDIT_EXPORT_SIZE_EXCEEDED'
                    or isinstance(exc,AuditFileStorageError) and exc.code=='FILE_SIZE_EXCEEDED'):
                raise AuditExportWorkerError('AUDIT_EXPORT_SIZE_EXCEEDED') from None
            raise AuditExportWorkerError('AUDIT_EXPORT_RENDER_FAILED') from None
