"""Recover only actual registered sources; success replay never re-finishes Jobs."""
from .worker_publish import AuditExportWorkerPublish
from .worker_render import AuditRenderContext, StagedAuditExport
from .worker_capture import AuditExportWorkerError
from .render_plan import AuditRenderPlan
from .render_export import RenderedAuditExport, build_audit_export_manifest
from .export_contract import AuditExportAuthorityRequest
from .export_result import AuditExportResult
from .submit_export import AcceptedAuditExport
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate, AuditFileContent
from plm_assistant.modules.document.application.audit_export_metadata import AuditRegisteredFileRequest, AuditFileMetadata
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef


class AuditExportWorkerRecover(AuditExportWorkerPublish):
    def _read(self, c):
        with self._uow() as tx:
            intent = self._repository.peek_created(tx, export_id=c.export_id)
            self._intent(intent, c)
            request = AuditExportAuthorityRequest(intent.export_id, intent.actor_id,
                intent.spec.scope, intent.spec.project_id, 'PUBLISH')
            if self._authority.assert_current(tx, request=request) is not None:raise AuditExportWorkerError()
            if self._repository.get_created(tx, export_id=c.export_id) != intent:raise AuditExportWorkerError()
            accepted = self._repository.get_accepted(tx, intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent != intent or accepted.job_id != c.job_id:
                raise AuditExportWorkerError()
            accepted.__post_init__()
            queue_request = AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,
                intent.spec.project_id,intent.trace_id,intent.policy_version)
            refs = AuditExportJobRef(accepted.job_id,accepted.event_id)
            if self._queue.find_export(tx, request=queue_request) != refs:raise AuditExportWorkerError()
            result = self._results.get(tx, export_id=c.export_id)
            plan = self._plans.find(tx, export_id=c.export_id,job_id=c.job_id,fencing_token=c.fencing_token)
            if type(plan) is not AuditRenderPlan:raise AuditExportWorkerError()
            plan.__post_init__()
            if plan.worker_ref != c.worker_ref:raise AuditExportWorkerError('STALE_LEASE')
            if result is None:
                claim = self._lease(tx,c,intent)
            else:
                if type(result) is not AuditExportResult:raise AuditExportWorkerError()
                result.__post_init__()
                if (result.render_attempt_id,result.file_id) != (plan.render_attempt_id,plan.file_id):raise AuditExportWorkerError()
                claim = self._completion.assert_succeeded(tx,request=queue_request,refs=refs,
                    fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            if claim.attempt_no != plan.attempt_no:raise AuditExportWorkerError()
            capture = self._captures.read_capture(tx,request=request)
            self._result(capture,intent)
            context = AuditRenderContext(intent,capture,plan)
            coordinate = AuditFileCoordinate(plan.file_id,intent.spec.scope,intent.spec.project_id)
            metadata = self._files.read_registered(tx,request=AuditRegisteredFileRequest(
                intent.export_id,intent.actor_id,intent.trace_id,coordinate))
            if type(metadata) is not AuditFileMetadata:raise AuditExportWorkerError()
            metadata.__post_init__()
            content = metadata.content
            rendered = RenderedAuditExport(intent.export_id,content.size_bytes,content.sha256.hex(),
                capture.member_count,build_audit_export_manifest(intent,capture,
                    file_sha256=content.sha256.hex(),byte_count=content.size_bytes))
            staged = StagedAuditExport(context,rendered,content)
            self._metadata(metadata,self._file_request(staged),'STAGED' if result is None else 'AVAILABLE')
            if result is not None and (result.file_sha256,result.byte_count,result.manifest_bytes) != (
                    content.sha256,content.size_bytes,rendered.manifest_bytes):raise AuditExportWorkerError()
            if self._authority.assert_current(tx,request=request) is not None:raise AuditExportWorkerError()
            if result is None and self._lease(tx,c,intent) != claim:raise AuditExportWorkerError()
            tx.commit()
            return staged,result

    def recover(self,command):
        """Restart using DB facts, not an in-memory staged DTO or client hash.

        Internal Worker result only, NOT a current HTTP Session/download permit.
        Expired/taken-over/cancelled attempts cannot reuse their old files.
        """
        staged,result = self._run(command,self._read)
        try:
            shape = self._storage.inspect(staged.content)  # Actual hashes outside UOW.
            if result is not None:
                if shape != 'FINAL_VERIFIED':raise AuditExportWorkerError('AUDIT_EXPORT_CONTENT_UNAVAILABLE')
                again,original = self._run(command,self._read)  # Reauthorization after physical I/O.
                if again != staged or original != result:raise AuditExportWorkerError()
                return original  # Never renew/re-finish/append a second Audit/result.
            mode = {'STAGE_ONLY':'new','FINAL_VERIFIED':'final_only','LINKED_PAIR':'linked_pair'}.get(shape)
            if mode is None:raise AuditExportWorkerError('AUDIT_EXPORT_CONTENT_UNAVAILABLE')
            identity = self._identity()
            self._run(command,lambda c:self._preflight(c,staged,identity))
            proof = self._storage.promote(staged.content,mode=mode)
            if type(proof) is not AuditFileContent or proof != staged.content:raise AuditExportWorkerError()
            return self._run(command,lambda c:self._publish(c,staged,identity))
        except AuditExportWorkerError:raise
        except Exception:raise AuditExportWorkerError('AUDIT_EXPORT_CONTENT_UNAVAILABLE') from None
