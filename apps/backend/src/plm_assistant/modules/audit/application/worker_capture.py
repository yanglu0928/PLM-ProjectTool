"""Actual accepted export/current authority/lease/capture in one fresh atomic UOW."""
from dataclasses import dataclass
from datetime import datetime
from re import fullmatch
from typing import Protocol
from uuid import UUID
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint
from .submit_export import AuditExportIntent,AcceptedAuditExport
from .export_contract import AuditExportAuthorityRequest,AuditExportCurrentAuthorityPort
from .current_export_authority import AuditExportCurrentAuthorityError
from .capture_contract import CapturedAuditExport,AuditCaptureError
from ..domain.capture_membership import MEMBERSHIP_VERSION


class AuditExportWorkerError(RuntimeError):
    def __init__(self,code="AUDIT_UNAVAILABLE"):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class AuditExportCaptureCommand:
    export_id: UUID
    job_id: UUID
    fencing_token: int
    worker_ref: str

    def __post_init__(self):
        if type(self.export_id) is not UUID or not self.export_id.int:
            raise AuditExportWorkerError("VALIDATION_FAILED")
        try:validate_checkpoint(job_id=self.job_id,fencing_token=self.fencing_token,worker_ref=self.worker_ref)
        except JobLeaseError:raise AuditExportWorkerError("VALIDATION_FAILED") from None


class AuditExportWorkerRepositoryPort(Protocol):
    def peek_created(self,tx:object,*,export_id:UUID)->AuditExportIntent|None: ...
    def get_created(self,tx:object,*,export_id:UUID)->AuditExportIntent|None: ...
    def get_accepted(self,tx:object,*,intent:AuditExportIntent)->AcceptedAuditExport|None: ...
    def is_retryable_deadlock(self,error:Exception)->bool: ...


class AuditExportWorkerCapture:
    def __init__(self,*,unit_of_work,repository:AuditExportWorkerRepositoryPort,
                 authority:AuditExportCurrentAuthorityPort,queue,leases,captures):
        if any(v is None for v in (unit_of_work,repository,authority,queue,leases,captures)):
            raise ValueError("Worker capture dependencies required")
        self._uow,self._repository,self._authority=unit_of_work,repository,authority
        self._queue,self._leases,self._captures=queue,leases,captures

    def capture(self,command:AuditExportCaptureCommand)->CapturedAuditExport:
        if type(command) is not AuditExportCaptureCommand:raise AuditExportWorkerError("VALIDATION_FAILED")
        command.__post_init__()
        for attempt in range(3):
            try:return self._capture(command)
            except Exception as exc:
                if self._repository.is_retryable_deadlock(exc) is True:
                    if attempt<2:continue
                    raise AuditExportWorkerError() from None
                if isinstance(exc,AuditExportWorkerError):raise
                if isinstance(exc,(AuditExportCurrentAuthorityError,JobLeaseError)):
                    raise AuditExportWorkerError(exc.code) from None
                if isinstance(exc,AuditCaptureError) and exc.reason=="LIMIT_EXCEEDED":
                    raise AuditExportWorkerError("AUDIT_EXPORT_LIMIT_EXCEEDED") from None
                raise AuditExportWorkerError() from None

    @staticmethod
    def _intent(value,command):
        if type(value) is not AuditExportIntent or value.export_id!=command.export_id:raise AuditExportWorkerError()
        value.__post_init__()

    def _lease(self,tx,command,intent):
        job=self._leases.check_current(tx,job_id=command.job_id,fencing_token=command.fencing_token,worker_ref=command.worker_ref)
        if (type(job) is not ClaimedJob or job.job_id!=command.job_id or job.job_type!="AUDIT_EXPORT"
                or (job.scope,job.project_id,job.trace_id)!=(intent.spec.scope,intent.spec.project_id,str(intent.trace_id))
                or type(job.fencing_token) is not int or job.fencing_token!=command.fencing_token
                or type(job.attempt_no) is not int or job.attempt_no<1
                or job.payload_refs!=dict(export_id=str(intent.export_id),policy_version=intent.policy_version)):
            raise AuditExportWorkerError()

    @staticmethod
    def _result(result,intent):
        if (type(result) is not CapturedAuditExport
                or (result.export_id,result.actor_id,result.scope,result.project_id,result.requested_at,result.intent_hash,
                    result.policy_version,result.projection_version,result.format_version)
                    !=(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.requested_at,intent.intent_hash,
                       intent.policy_version,intent.projection_version,intent.format_version)
                or type(result.member_count) is not int or result.member_count<0
                or result.membership_version!=MEMBERSHIP_VERSION or type(result.membership_hash) is not str
                or not fullmatch(r"[0-9a-f]{64}",result.membership_hash)
                or type(result.captured_at) is not datetime or result.captured_at.tzinfo is None
                or result.captured_at.utcoffset() is None or result.captured_at<intent.requested_at):
            raise AuditExportWorkerError()

    def _capture(self,c):
        with self._uow() as tx:
            intent=self._repository.peek_created(tx,export_id=c.export_id)
            self._intent(intent,c)
            request=AuditExportAuthorityRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,"CAPTURE")
            if self._authority.assert_current(tx,request=request) is not None:raise AuditExportWorkerError()
            locked=self._repository.get_created(tx,export_id=c.export_id)
            self._intent(locked,c)
            if locked!=intent:raise AuditExportWorkerError()
            accepted=self._repository.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent or accepted.job_id!=c.job_id:raise AuditExportWorkerError()
            accepted.__post_init__()
            queued=self._queue.find_export(tx,request=AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version))
            if type(queued) is not AuditExportJobRef or (queued.job_id,queued.event_id)!=(accepted.job_id,accepted.event_id):raise AuditExportWorkerError()
            queued.__post_init__()
            self._lease(tx,c,intent)
            result=self._captures.capture(tx,request=request)
            self._result(result,intent)
            if self._authority.assert_current(tx,request=request) is not None:raise AuditExportWorkerError()
            self._lease(tx,c,intent)  # No expired lease can commit even after slow capture.
            tx.commit()
            return result
