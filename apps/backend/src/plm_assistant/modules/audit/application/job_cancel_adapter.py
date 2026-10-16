"""Explicit Audit cancellation Owner; no authority from dispatch hints."""
from .request_export_cancel import RequestAuditJobCancel,AuditExportCancelReceipt,AuditExportCancelRequestError
from plm_assistant.modules.jobs.application.cancel_request import RequestProjectJobCancel,JobCancelResult,JobCancelError

class AuditJobCancelOwner:
    def __init__(self,*,requests):
        if requests is None:raise ValueError('Actual Audit cancellation service required')
        self._requests=requests
    def cancel(self,c,*,idempotency_key):
        if type(c) is not RequestProjectJobCancel:raise JobCancelError('VALIDATION_FAILED')
        c.__post_init__()
        command=RequestAuditJobCancel(c.job_id,'PROJECT',c.project_id,c.session_token,c.csrf_token,c.trace_id,c.reason,c.expected_version)
        try:result=self._requests.request_job(command,idempotency_key=idempotency_key)
        except AuditExportCancelRequestError as exc:
            code={'VERSION_CONFLICT':'CONFLICT_VERSION','AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND',
                'RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND','CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY',
                'VALIDATION_FAILED':'VALIDATION_FAILED','LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED'}.get(exc.code,'JOB_UNAVAILABLE')
            raise JobCancelError(code) from None
        if type(result) is not AuditExportCancelReceipt or result.job_id!=c.job_id:raise JobCancelError()
        result.__post_init__()
        return JobCancelResult(result.job_id,result.state,result.changed,result.lock_version)
