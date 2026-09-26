"""CR-AUD-004: terminal-only internal safety Owner, NEVER business authority."""
from uuid import UUID
from .heartbeat_coordinator import AuditHeartbeatSupervisor
from .worker_capture import AuditExportCaptureCommand, AuditExportWorkerCapture, AuditExportWorkerError
from .submit_export import AcceptedAuditExport
from .public import AuditEventDraft
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult
from plm_assistant.modules.jobs.application.lease import JobLeaseError

TERMINAL_REASONS=frozenset({'AUTH_ACCESS_DENIED','RESOURCE_NOT_FOUND','LICENSE_OPERATION_DENIED',
    'AUDIT_EXPORT_LIMIT_EXCEEDED','AUDIT_EXPORT_CONTENT_UNAVAILABLE'})


class AuditExportWorkerTermination:
    def __init__(self,*,unit_of_work,repository,queue,failure,audit,system_actor,supervisor):
        if any(v is None for v in (unit_of_work,repository,queue,failure,audit,system_actor)) or type(supervisor) is not AuditHeartbeatSupervisor:
            raise ValueError('Safety termination owned dependencies required')
        self._uow,self._repo,self._queue,self._failure=unit_of_work,repository,queue,failure
        self._audit,self._actor,self._supervisor=audit,system_actor,supervisor

    def _identity(self):
        try:
            value=self._actor.assert_current()
            if type(value) is not UUID or not value.int:raise ValueError()
            return value
        except Exception:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE') from None

    def terminate(self,command,*,reason_code):
        if type(command) is not AuditExportCaptureCommand or type(reason_code) is not str or reason_code not in TERMINAL_REASONS:
            raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        # Same supervisor as the runner. No claim, body read, file operation or User bypass.
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._terminate(command,reason_code)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,JobLeaseError):raise AuditExportWorkerError(exc.code) from None
                    raise AuditExportWorkerError() from None

    def _terminate(self,c,reason):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.get_created(tx,export_id=c.export_id)
            AuditExportWorkerCapture._intent(intent,c)
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:
                raise AuditExportWorkerError()
            accepted.__post_init__()
            request=AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version)
            refs=AuditExportJobRef(accepted.job_id,accepted.event_id)
            actual=self._queue.find_export(tx,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs:raise AuditExportWorkerError()
            actual.__post_init__()
            event_id=self._audit.append(tx,AuditEventDraft(trace_id=intent.trace_id,event_scope=intent.spec.scope,
                target_project_id=intent.spec.project_id,actor_type='SYSTEM',actor_id=identity,
                original_actor_id=intent.actor_id,actor_hint_digest=None,action='AUDIT_EXPORT_FAILED',outcome='FAILED',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=c.job_id,
                reason_code=reason,before_state='RUNNING',after_state='FAILED'))
            if type(event_id) is not UUID or not event_id.int:raise AuditExportWorkerError()
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            result=self._failure.fail_current(tx,request=request,refs=refs,fencing_token=c.fencing_token,
                worker_ref=c.worker_ref,error_code=reason,retryable=False,delay_seconds=0)
            if type(result) is not AuditExportFailureResult or result.state!='FAILED':raise AuditExportWorkerError()
            tx.commit()  # Real current Lease checked LAST; no work between conversion and commit.
            return result
