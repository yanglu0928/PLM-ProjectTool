"""Owned terminal technical facts, never permission to submit a new generation."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from .lease import JobLeaseError
from .audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef

@dataclass(frozen=True, slots=True)
class AuditUserRetryJobFailure:
    job_id: UUID
    lock_version: int
    attempt_no: int
    started_at: datetime
    completed_at: datetime

    def __post_init__(self):
        if (type(self.job_id) is not UUID or not self.job_id.int
            or type(self.lock_version) is not int or not 0<=self.lock_version<=9223372036854775807
            or type(self.attempt_no) is not int or self.attempt_no!=3
            or any(type(t) is not datetime or t.tzinfo is None or t.utcoffset() is None for t in (self.started_at,self.completed_at))
            or self.started_at>self.completed_at):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')

class AuditUserRetryJobSources:
    def __init__(self, *, queue, repository):
        if queue is None or repository is None: raise ValueError('Actual Job retry sources required')
        self._queue,self._repo=queue,repository

    def read_failed(self, tx, *, request, refs, expected_version):
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:
            raise JobLeaseError('VALIDATION_FAILED')
        request.__post_init__(); refs.__post_init__()
        if type(expected_version) is not int or not 0<=expected_version<=9223372036854775807:
            raise JobLeaseError('VALIDATION_FAILED')
        try:
            actual=self._queue.find_export(tx,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs: raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            result=self._repo.read_failed(tx,request=request,refs=refs,expected_version=expected_version)
            if type(result) is not AuditUserRetryJobFailure: raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            result.__post_init__()
            if result.job_id!=refs.job_id or result.lock_version!=expected_version: raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return result
        except JobLeaseError: raise
        except Exception: raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
