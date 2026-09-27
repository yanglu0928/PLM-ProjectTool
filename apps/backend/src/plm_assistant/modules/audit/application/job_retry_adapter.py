"""Audit mutation authority stays in its owned write UOW, never a Job read hint."""
from .request_user_retry import RequestAuditUserRetry, AuditUserRetryError
from .retry_generation import AuditExportRetryGeneration
from plm_assistant.modules.jobs.application.retry_request import RequestJobRetry, JobRetryResult, JobRetryError

class AuditJobRetryOwner:
    def __init__(self,*,requests):
        if requests is None:raise ValueError('Actual Audit retry service required')
        self._requests=requests
    def retry(self,c,*,idempotency_key):
        if type(c) is not RequestJobRetry:raise JobRetryError('VALIDATION_FAILED')
        c.__post_init__()
        scope='PROJECT' if c.project_id is not None else 'DEPLOYMENT'
        try:
            value=self._requests.retry(RequestAuditUserRetry(c.job_id,scope,c.project_id,c.session_token,
                c.csrf_token,c.trace_id,c.expected_version),idempotency_key=idempotency_key)
        except AuditUserRetryError as exc:
            code={'VERSION_CONFLICT':'CONFLICT_VERSION','AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND',
                'JOB_NOT_RETRYABLE':'JOB_NOT_RETRYABLE','RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED',
                'VALIDATION_FAILED':'VALIDATION_FAILED'}.get(exc.code,'JOB_UNAVAILABLE')
            raise JobRetryError(code) from None
        if (type(value) is not AuditExportRetryGeneration or value.source_job_id!=c.job_id
            or value.expected_source_version!=c.expected_version):raise JobRetryError()
        value.__post_init__()
        return JobRetryResult(c.job_id,value.new_job_id,c.project_id,scope,value.created_at)
