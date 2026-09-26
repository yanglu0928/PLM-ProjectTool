"""Short current-authorized Owner heartbeat; no periodic scheduler/file work."""
from .worker_capture import AuditExportWorkerCapture, AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease import ClaimedJob


class AuditExportWorkerHeartbeat(AuditExportWorkerCapture):
    def __init__(self, *, renewals, **kwargs):
        if renewals is None:
            raise ValueError('Caller-UOW renewal dependency required')
        super().__init__(**kwargs)
        self._renewals = renewals

    def heartbeat(self, command, *, lease_seconds, stage='RENDER'):
        if (type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600
                or type(stage) is not str or stage not in {'CAPTURE','RENDER','PUBLISH'}):
            raise AuditExportWorkerError('VALIDATION_FAILED')
        return self._run(command, lambda c: self._heartbeat(c, lease_seconds, stage))

    def _heartbeat(self, command, seconds, stage):
        with self._uow() as tx:
            intent, request, before = self._authorized(tx, command, stage)
            renewed = self._renewals.renew_current(tx, job_id=command.job_id,
                fencing_token=command.fencing_token, worker_ref=command.worker_ref, lease_seconds=seconds)
            if type(renewed) is not ClaimedJob or renewed != before:
                raise AuditExportWorkerError()
            if self._authority.assert_current(tx, request=request) is not None:
                raise AuditExportWorkerError()
            if self._lease(tx, command, intent) != before:
                raise AuditExportWorkerError()
            tx.commit()
            return renewed
