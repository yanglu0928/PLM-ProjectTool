"""Audit-specific technical failure in caller UOW; NEVER Owner authorization."""
from dataclasses import dataclass
from .audit_export_enqueue import AuditExportJobRequest, AuditExportJobRef
from .audit_export_complete import AuditExportJobCompletion
from .lease import ClaimedJob, JobLeaseError
from .lease_checkpoint import validate_checkpoint
from .failure_proof import FailedJobProof
from .retry_proof import RetryTransitionProof

ERROR_CODES = frozenset({'AUDIT_UNAVAILABLE','AUDIT_EXPORT_CONTENT_UNAVAILABLE',
    'AUDIT_EXPORT_LIMIT_EXCEEDED','AUTH_ACCESS_DENIED','RESOURCE_NOT_FOUND','LICENSE_OPERATION_DENIED',
    'SYSTEM_ACTOR_UNAVAILABLE','AUDIT_HEARTBEAT_STOP_TIMEOUT','AUDIT_HEARTBEAT_CAPACITY','AUDIT_HEARTBEAT_NOT_READY'})


@dataclass(frozen=True,slots=True)
class AuditExportFailureResult:
    claim: ClaimedJob
    state: str

    def __post_init__(self):
        if type(self.claim) is not ClaimedJob or type(self.state) is not str or self.state not in {'RETRY_WAIT','FAILED'}:
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')


class AuditExportJobFailure:
    def __init__(self, *, queue, leases):
        if queue is None or leases is None:
            raise ValueError('Owned failure dependencies required')
        self._queue,self._leases=queue,leases

    def assert_retry_transition(self,transaction,*,request,refs,fencing_token,worker_ref,attempt_no):
        if (type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef
                or type(attempt_no) is not int or not 1<=attempt_no<=3):raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            actual.__post_init__()
            proof=self._leases.check_retry_transition(transaction,job_id=refs.job_id,fencing_token=fencing_token,
                worker_ref=worker_ref,delay_seconds={1:5,2:15,3:0}[attempt_no])
            if type(proof) is not RetryTransitionProof:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            proof.__post_init__();claim=AuditExportJobCompletion._claim(proof.claim,request,refs,fencing_token)
            if claim.attempt_no!=attempt_no or proof.state!=('FAILED' if attempt_no==3 else 'RETRY_WAIT'):raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return proof
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def inspect_current(self,transaction,*,request,refs,fencing_token,worker_ref):
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            actual.__post_init__()
            claim=AuditExportJobCompletion._claim(self._leases.check_current(transaction,job_id=refs.job_id,
                fencing_token=fencing_token,worker_ref=worker_ref),request,refs,fencing_token)
            if claim.attempt_no>3:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return claim
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def assert_failed(self,transaction,*,request,refs,fencing_token,worker_ref,error_code):
        """Only technical source verification; caller MUST verify owned Audit receipt."""
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:
            raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        except Exception:raise JobLeaseError('VALIDATION_FAILED') from None
        if type(error_code) is not str or error_code not in ERROR_CODES:raise JobLeaseError('VALIDATION_FAILED')
        try:
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            actual.__post_init__()
            proof=self._leases.check_failed(transaction,job_id=refs.job_id,fencing_token=fencing_token,
                worker_ref=worker_ref,error_code=error_code)
            if type(proof) is not FailedJobProof:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            proof.__post_init__()
            claim=AuditExportJobCompletion._claim(proof.claim,request,refs,fencing_token)
            if claim.attempt_no>3 or proof.error_code!=error_code:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return proof
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def fail_current(self,transaction,*,request,refs,fencing_token,worker_ref,error_code,retryable,delay_seconds=0):
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:
            raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        except Exception:
            raise JobLeaseError('VALIDATION_FAILED') from None
        if (type(error_code) is not str or error_code not in ERROR_CODES or type(retryable) is not bool
                or type(delay_seconds) is not int or not 0 <= delay_seconds <= 86400):
            raise JobLeaseError('VALIDATION_FAILED')
        try:
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef or actual != refs:
                raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            actual.__post_init__()
            claim=AuditExportJobCompletion._claim(self._leases.check_current(transaction,job_id=refs.job_id,
                fencing_token=fencing_token,worker_ref=worker_ref),request,refs,fencing_token)
            if claim.attempt_no>3:
                raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            state=self._leases.retry_or_fail(transaction,job_id=refs.job_id,fencing_token=fencing_token,
                worker_ref=worker_ref,error_code=error_code,retryable=retryable,delay_seconds=delay_seconds)
            expected='RETRY_WAIT' if retryable and claim.attempt_no<3 else 'FAILED'
            if type(state) is not str or state!=expected:
                raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return AuditExportFailureResult(claim,state)
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
