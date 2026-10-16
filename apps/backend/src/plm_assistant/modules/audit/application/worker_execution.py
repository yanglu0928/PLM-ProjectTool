"""Current-authorized DB-only execution hint; never permission or file existence proof."""
from .worker_recover import AuditExportWorkerRecover
from .worker_capture import AuditExportWorkerError
from .export_contract import AuditExportAuthorityRequest
from .export_result import AuditExportResult
from .render_plan import AuditRenderPlan
from .submit_export import AcceptedAuditExport
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate
from plm_assistant.modules.document.application.audit_export_metadata import AuditRegisteredFileRequest, AuditFileMetadata
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob


class AuditExportWorkerExecution(AuditExportWorkerRecover):
    def classify(self, command):
        return self._run(command, self._classify)

    def _classify(self, c):
        with self._uow() as tx:
            intent = self._repository.peek_created(tx, export_id=c.export_id)
            self._intent(intent, c)
            request = AuditExportAuthorityRequest(intent.export_id,intent.actor_id,
                intent.spec.scope,intent.spec.project_id,'PUBLISH')
            if self._authority.assert_current(tx,request=request) is not None:
                raise AuditExportWorkerError()
            if self._repository.get_created(tx,export_id=c.export_id) != intent:
                raise AuditExportWorkerError()
            accepted = self._repository.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent != intent or accepted.job_id != c.job_id:
                raise AuditExportWorkerError()
            accepted.__post_init__()
            qr = AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,
                intent.spec.project_id,intent.trace_id,intent.policy_version)
            refs = AuditExportJobRef(accepted.job_id,accepted.event_id)
            if self._queue.find_export(tx,request=qr) != refs:
                raise AuditExportWorkerError()
            result = self._results.get(tx,export_id=c.export_id)
            plan = self._plans.find(tx,export_id=c.export_id,job_id=c.job_id,fencing_token=c.fencing_token)
            if plan is not None:
                if type(plan) is not AuditRenderPlan:
                    raise AuditExportWorkerError()
                plan.__post_init__()
                if (plan.export_id,plan.job_id,plan.fencing_token,plan.worker_ref) != (c.export_id,c.job_id,c.fencing_token,c.worker_ref):
                    raise AuditExportWorkerError('STALE_LEASE')
            if result is not None:
                if type(result) is not AuditExportResult or plan is None:
                    raise AuditExportWorkerError()
                result.__post_init__()
                if (result.export_id,result.render_attempt_id,result.file_id) != (c.export_id,plan.render_attempt_id,plan.file_id):
                    raise AuditExportWorkerError()
                claim = self._completion.assert_succeeded(tx,request=qr,refs=refs,
                    fencing_token=c.fencing_token,worker_ref=c.worker_ref)
                path = 'PUBLISHED'
            else:
                claim = self._lease(tx,c,intent)
                path = 'RENDER'
                if plan is not None:
                    coordinate = AuditFileCoordinate(plan.file_id,intent.spec.scope,intent.spec.project_id)
                    metadata = self._files.read_registered(tx,request=AuditRegisteredFileRequest(
                        intent.export_id,intent.actor_id,intent.trace_id,coordinate))
                    if metadata is not None:
                        if type(metadata) is not AuditFileMetadata:
                            raise AuditExportWorkerError()
                        metadata.__post_init__()
                        if (metadata.export_id,metadata.actor_id,metadata.registration_trace_id,metadata.content.coordinate) != (
                                intent.export_id,intent.actor_id,intent.trace_id,coordinate):
                            raise AuditExportWorkerError()
                        path = 'RECOVER'
            if (type(claim) is not ClaimedJob or claim.job_id != c.job_id
                    or type(claim.fencing_token) is not int or claim.fencing_token != c.fencing_token
                    or type(claim.attempt_no) is not int or claim.attempt_no < 1
                    or claim.job_type != 'AUDIT_EXPORT'
                    or (claim.scope,claim.project_id,claim.trace_id) != (intent.spec.scope,intent.spec.project_id,str(intent.trace_id))
                    or claim.payload_refs != dict(export_id=str(intent.export_id),policy_version=intent.policy_version)):
                raise AuditExportWorkerError()
            if plan is not None and claim.attempt_no != plan.attempt_no:
                raise AuditExportWorkerError()
            if self._authority.assert_current(tx,request=request) is not None:
                raise AuditExportWorkerError()
            if result is None and self._lease(tx,c,intent) != claim:
                raise AuditExportWorkerError()
            return path  # Read-only UOW, hint rechecked by every subsequent operation.
