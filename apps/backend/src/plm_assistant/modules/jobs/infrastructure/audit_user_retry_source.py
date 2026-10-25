"""Jobs-only checks under caller Root/pair lock; no writes or own commit."""
from sqlalchemy import select
from ..application.audit_user_retry_source import AuditUserRetryJobFailure
from ..application.lease import JobLeaseError
from .lease_repository import SqlAlchemyJobLeaseRepository
from .orm import JobRow, JobAttemptRow

class SqlAlchemyAuditUserRetryJobSources:
    def read_failed(self,tx,*,request,refs,expected_version):
        leases=SqlAlchemyJobLeaseRepository()
        session=leases._session(tx)
        job=session.scalar(select(JobRow).where(JobRow.job_id==refs.job_id).with_for_update(of=JobRow).execution_options(populate_existing=True))
        if job is None: raise JobLeaseError('RESOURCE_NOT_FOUND')
        if ((job.owner_module,job.job_type,job.scope,job.project_id,job.actor_ref,job.trace_id,job.idempotency_key)
            !=('audit','AUDIT_EXPORT',request.scope,request.project_id,request.actor_id,str(request.trace_id),str(request.export_id))
            or job.payload_refs!=dict(export_id=str(request.export_id),policy_version=request.policy_version)
            or job.max_attempts!=3): raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        if job.lock_version!=expected_version: raise JobLeaseError('VERSION_CONFLICT')
        if job.state!='FAILED': raise JobLeaseError('JOB_NOT_RETRYABLE')
        attempt=session.scalar(select(JobAttemptRow).where(JobAttemptRow.job_id==job.job_id,
            JobAttemptRow.fencing_token==job.fencing_token).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
        if attempt is None: raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        if attempt.error_code!='AUDIT_UNAVAILABLE': raise JobLeaseError('JOB_NOT_RETRYABLE')
        if job.attempt_count!=3 or attempt.attempt_no!=3: raise JobLeaseError('JOB_NOT_RETRYABLE')
        proof=leases.check_retry_transition(tx,job_id=job.job_id,fencing_token=job.fencing_token,
            worker_ref=attempt.worker_ref,delay_seconds=0)
        if (proof.state!='FAILED' or proof.claim.job_id!=refs.job_id
            or job.created_at>proof.started_at or job.completed_at!=proof.completed_at):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        return AuditUserRetryJobFailure(job.job_id,job.lock_version,3,proof.started_at,proof.completed_at)
