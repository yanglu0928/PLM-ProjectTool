"""Controlled cancellation acknowledgement ONLY; no business authority or file I/O."""
from uuid import UUID
from .heartbeat_coordinator import AuditHeartbeatSupervisor
from .worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from .submit_export import AcceptedAuditExport,AuditExportSubmitService
from .request_export_cancel import AuditExportCancelReceipt
from .public import AuditEventDraft
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellationTarget,AuditExportCancellationError,AuditExportCancellationResult,AuditExportCancelFacts


class AuditExportWorkerCancel:
    def __init__(self,*,unit_of_work,repository,cancellations,sources,audit,system_actor,supervisor):
        if any(v is None for v in (unit_of_work,repository,cancellations,sources,audit,system_actor)) or type(supervisor) is not AuditHeartbeatSupervisor:
            raise ValueError('Owned safety cancellation dependencies required')
        self._uow,self._repo,self._cancel,self._sources,self._audit,self._actor,self._supervisor=unit_of_work,repository,cancellations,sources,audit,system_actor,supervisor

    def _identity(self):
        try:
            value=self._actor.assert_current()
            if type(value) is not UUID or not value.int:raise ValueError()
            return value
        except Exception:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE') from None

    def acknowledge(self,command):
        if type(command) is not AuditExportCaptureCommand:raise AuditExportWorkerError('VALIDATION_FAILED')
        command.__post_init__()
        with self._supervisor.stopped(command):
            for attempt in range(3):
                try:return self._acknowledge(command)
                except Exception as exc:
                    if self._repo.is_retryable_deadlock(exc) is True:
                        if attempt<2:continue
                        raise AuditExportWorkerError() from None
                    if isinstance(exc,AuditExportWorkerError):raise
                    if isinstance(exc,AuditExportCancellationError):raise AuditExportWorkerError(exc.code) from None
                    # Failed source proof details and DB messages never escape.
                    raise AuditExportWorkerError() from None

    def _acknowledge(self,c):
        identity=self._identity()
        with self._uow() as tx:
            intent=self._repo.get_created(tx,export_id=c.export_id);AuditExportWorkerCapture._intent(intent,c)
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            target=AuditExportCancellationTarget(AuditExportSubmitService._queue_request(intent),AuditExportJobRef(accepted.job_id,accepted.event_id))
            facts=self._cancel.read_facts(tx,target=target)
            if type(facts) is not AuditExportCancelFacts or facts.job_id!=c.job_id or facts.state!='CANCEL_REQUESTED':raise AuditExportWorkerError('STALE_LEASE')
            facts.__post_init__()
            first=self._sources.first_request(tx,accepted=accepted,facts=facts)
            if type(first) is not AuditExportCancelReceipt or first.job_id!=c.job_id or first.state!='CANCEL_REQUESTED' or first.changed is not True:raise AuditExportWorkerError()
            first.__post_init__()
            event_id=self._audit.append(tx,AuditEventDraft(trace_id=intent.trace_id,event_scope=intent.spec.scope,
                target_project_id=intent.spec.project_id,actor_type='SYSTEM',actor_id=identity,original_actor_id=intent.actor_id,
                actor_hint_digest=None,action='AUDIT_EXPORT_CANCELLED',outcome='SUCCESS',target_owner_module='jobs',
                target_object_type='JOB-01',target_object_id=c.job_id,reason_code='USER_REQUESTED',before_state='CANCEL_REQUESTED',after_state='CANCELLED'))
            if type(event_id) is not UUID or not event_id.int:raise AuditExportWorkerError()
            if self._identity()!=identity:raise AuditExportWorkerError('SYSTEM_ACTOR_UNAVAILABLE')
            result=self._cancel.acknowledge_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref)
            if (type(result) is not AuditExportCancellationResult or result.job_id!=c.job_id
                    or result.state!='CANCELLED' or result.changed is not True):raise AuditExportWorkerError()
            result.__post_init__()
            tx.commit()  # Current Worker/fence/actual lifetime checked LAST; no I/O after ack.
            return result
