"""Original immutable acceptance and final failure; caller still must authorize."""
from dataclasses import dataclass
from uuid import UUID
from .submit_export import AcceptedAuditExport
from .worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobFailure
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import JobLeaseError

@dataclass(frozen=True, slots=True)
class AuditUserRetrySource:
    accepted: AcceptedAuditExport
    failure: AuditUserRetryJobFailure
    failure_event_id: UUID

    def __post_init__(self):
        if (type(self.accepted) is not AcceptedAuditExport or type(self.failure) is not AuditUserRetryJobFailure
            or type(self.failure_event_id) is not UUID or not self.failure_event_id.int):
            raise AuditExportWorkerError()
        self.accepted.__post_init__(); self.failure.__post_init__()
        if self.accepted.job_id!=self.failure.job_id or self.accepted.accepted_at>self.failure.started_at:
            raise AuditExportWorkerError()

class AuditUserRetrySourceReader:
    def __init__(self, *, repository, jobs, failures):
        if any(v is None for v in (repository,jobs,failures)): raise ValueError('Actual owned retry sources required')
        self._repo,self._jobs,self._failures=repository,jobs,failures

    def read(self,tx,*,accepted,expected_version):
        if type(accepted) is not AcceptedAuditExport: raise AuditExportWorkerError()
        accepted.__post_init__(); intent=accepted.intent
        try:
            if self._repo.get_created(tx,export_id=intent.export_id)!=intent or self._repo.get_accepted(tx,intent=intent)!=accepted:
                raise AuditExportWorkerError()
            failure=self._jobs.read_failed(tx,request=AuditExportJobRequest(intent.export_id,intent.actor_id,
                intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version),
                refs=AuditExportJobRef(accepted.job_id,accepted.event_id),expected_version=expected_version)
            if type(failure) is not AuditUserRetryJobFailure: raise AuditExportWorkerError()
            failure.__post_init__()
            if failure.job_id!=accepted.job_id or failure.lock_version!=expected_version:
                raise AuditExportWorkerError()
            event=self._failures.read_failure(tx,accepted=accepted,failure=failure)
            return AuditUserRetrySource(accepted,failure,event)
        except (AuditExportWorkerError,JobLeaseError): raise
        except Exception: raise AuditExportWorkerError() from None
