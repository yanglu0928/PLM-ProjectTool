"""Audit-specific current-lease completion in caller UOW; refs are not authority."""
from typing import Protocol
from .audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef,AuditExportEnqueueError,AuditExportJobQueuePort
from .lease_checkpoint import validate_checkpoint
from .lease import ClaimedJob,JobLeaseError


class AuditExportCompletionLeasePort(Protocol):
    def check_succeeded(self,transaction:object,*,job_id,fencing_token:int,worker_ref:str)->ClaimedJob: ...
    def check_current(self,transaction:object,*,job_id,fencing_token:int,worker_ref:str)->ClaimedJob: ...
    def finish(self,transaction:object,*,job_id,fencing_token:int,worker_ref:str)->ClaimedJob: ...


class AuditExportJobCompletionPort(Protocol):
    def assert_succeeded(self,transaction:object,*,request:AuditExportJobRequest,refs:AuditExportJobRef,
                         fencing_token:int,worker_ref:str)->ClaimedJob: ...
    def complete_current(self,transaction:object,*,request:AuditExportJobRequest,refs:AuditExportJobRef,
                         fencing_token:int,worker_ref:str)->ClaimedJob: ...


class AuditExportJobCompletion:
    """Call LAST after current Owner auth/publication checks; then commit promptly.

    No self UOW, callback, commit, authority, result or physical file operations.
    Holding locks is not permission. Success replay belongs to the Audit Owner's
    authorized immutable result read, not reviving or re-finishing a terminal Job.
    """
    def __init__(self,*,queue:AuditExportJobQueuePort,leases:AuditExportCompletionLeasePort):
        if queue is None or leases is None:raise ValueError('Job completion dependencies required')
        self._queue,self._leases=queue,leases

    @staticmethod
    def _claim(value,request,refs,token):
        if (type(value) is not ClaimedJob or value.job_id!=refs.job_id or value.job_type!='AUDIT_EXPORT'
                or (value.scope,value.project_id,value.trace_id)!=(request.scope,request.project_id,str(request.trace_id))
                or type(value.payload_refs) is not dict
                or value.payload_refs!=dict(export_id=str(request.export_id),policy_version=request.policy_version)
                or type(value.fencing_token) is not int or value.fencing_token!=token
                or type(value.attempt_no) is not int or not 0<value.attempt_no<2**31):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        return value

    def complete_current(self,transaction,*,request,refs,fencing_token,worker_ref):
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:
            raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        except (AuditExportEnqueueError,JobLeaseError):raise JobLeaseError('VALIDATION_FAILED') from None
        try:
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            actual.__post_init__()
            if actual!=refs:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            args=dict(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            before=self._claim(self._leases.check_current(transaction,**args),request,refs,fencing_token)
            after=self._claim(self._leases.finish(transaction,**args),request,refs,fencing_token)
            if after!=before:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return after
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def assert_succeeded(self,transaction,*,request,refs,fencing_token,worker_ref):
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:
            raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return self._claim(self._leases.check_succeeded(transaction,job_id=refs.job_id,
                fencing_token=fencing_token,worker_ref=worker_ref),request,refs,fencing_token)
        except (AuditExportEnqueueError,JobLeaseError):raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
