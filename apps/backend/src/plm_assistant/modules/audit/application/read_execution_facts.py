"""Controlled internal state hints; no business authority, file I/O or commit."""
from .worker_cancel import AuditExportWorkerCancel
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from .submit_export import AcceptedAuditExport,AuditExportSubmitService
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionFacts
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class AuditExportExecutionReader(AuditExportWorkerCancel):
    def __init__(self,*,execution_facts,**deps):
        if execution_facts is None:raise ValueError('Owned execution facts required')
        super().__init__(**deps);self._facts=execution_facts

    def read(self,command):
        if type(command) is not AuditExportCaptureCommand:raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._read(command)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,JobLeaseError):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _read(self,c):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.get_created(tx,export_id=c.export_id);AuditExportWorkerCapture._intent(intent,c)
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            request=AuditExportSubmitService._queue_request(intent);refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
            facts=self._facts.read(tx,request=request,refs=refs,fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            if type(facts) is not AuditExportExecutionFacts:raise AuditExportWorkerError()
            facts.__post_init__();AuditExportJobCompletion._claim(facts.claim,request,refs,c.fencing_token)
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            return facts  # No terminal receipt; later Owner must recheck actual sources.
