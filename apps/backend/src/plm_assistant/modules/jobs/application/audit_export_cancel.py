"""Trusted Audit Owner transaction cancellation; refs never authorize callers."""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID
import unicodedata
from .audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef, AuditExportEnqueueError
from .lease_checkpoint import validate_checkpoint
from .lease import JobLeaseError


class AuditExportCancellationError(RuntimeError):
    def __init__(self, code):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class AuditExportCancellationTarget:
    request: AuditExportJobRequest
    refs: AuditExportJobRef

    def __post_init__(self):
        if type(self.request) is not AuditExportJobRequest or type(self.refs) is not AuditExportJobRef:
            raise AuditExportCancellationError("VALIDATION_FAILED")
        try:self.request.__post_init__();self.refs.__post_init__()
        except AuditExportEnqueueError:
            raise AuditExportCancellationError("VALIDATION_FAILED") from None


@dataclass(frozen=True,slots=True)
class AuditExportCancellationResult:
    job_id: UUID
    state: str
    changed: bool

    def __post_init__(self):
        if (type(self.job_id) is not UUID or not self.job_id.int or type(self.changed) is not bool
                or type(self.state) is not str or self.state not in {"CANCEL_REQUESTED","CANCELLED","SUCCEEDED","FAILED"}
                or self.changed and self.state in {"SUCCEEDED","FAILED"}):
            raise AuditExportCancellationError("JOB_STORE_UNAVAILABLE")


def validate_target(target):
    if type(target) is not AuditExportCancellationTarget:raise AuditExportCancellationError("VALIDATION_FAILED")
    target.__post_init__()


def validate_cancel_request(*,target,requested_by,reason):
    validate_target(target)
    if (type(requested_by) is not UUID or not requested_by.int or type(reason) is not str
            or not 1<=len(reason)<=1024 or reason.strip()!=reason
            or any(unicodedata.category(char).startswith("C") for char in reason)):
        raise AuditExportCancellationError("VALIDATION_FAILED")


class AuditExportCancellationRepositoryPort(Protocol):
    def request_cancel(self,transaction:object,*,target:AuditExportCancellationTarget,requested_by:UUID,reason:str)->AuditExportCancellationResult: ...
    def acknowledge_cancel(self,transaction:object,*,target:AuditExportCancellationTarget,fencing_token:int,worker_ref:str)->AuditExportCancellationResult: ...
    def recover_expired_cancel(self,transaction:object,*,target:AuditExportCancellationTarget)->AuditExportCancellationResult: ...


class AuditExportCancellation:
    def __init__(self,*,repository:AuditExportCancellationRepositoryPort):
        if repository is None:raise ValueError("cancellation repository required")
        self._repository=repository

    @staticmethod
    def _result(target,result):
        if type(result) is not AuditExportCancellationResult or result.job_id!=target.refs.job_id:
            raise AuditExportCancellationError("JOB_STORE_UNAVAILABLE")
        result.__post_init__();return result

    def _call(self,transaction,target,method,**kwargs):
        try:return self._result(target,method(transaction,target=target,**kwargs))
        except AuditExportCancellationError:raise
        except Exception:raise AuditExportCancellationError("JOB_STORE_UNAVAILABLE") from None

    def request_cancel(self,transaction,*,target,requested_by,reason):
        validate_cancel_request(target=target,requested_by=requested_by,reason=reason)
        return self._call(transaction,target,self._repository.request_cancel,requested_by=requested_by,reason=reason)

    def acknowledge_cancel(self,transaction,*,target,fencing_token,worker_ref):
        validate_target(target)
        try:validate_checkpoint(job_id=target.refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        except JobLeaseError:raise AuditExportCancellationError("VALIDATION_FAILED") from None
        result=self._call(transaction,target,self._repository.acknowledge_cancel,fencing_token=fencing_token,worker_ref=worker_ref)
        if result.state!="CANCELLED":raise AuditExportCancellationError("JOB_STORE_UNAVAILABLE")
        return result

    def recover_expired_cancel(self,transaction,*,target):
        validate_target(target)
        result=self._call(transaction,target,self._repository.recover_expired_cancel)
        if result.state!="CANCELLED":raise AuditExportCancellationError("JOB_STORE_UNAVAILABLE")
        return result
