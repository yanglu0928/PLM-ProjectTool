"""Jobs-owned OutputGenerate cancellation in the caller's transaction."""
from __future__ import annotations
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from plm_assistant.modules.jobs.application.output_cancel import (
    OutputJobCancelError, OutputJobCancelResult,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow, JobLeaseRow, JobRow
class SqlAlchemyOutputJobCancellationRepository:
    def cancel_output(self, transaction: object, *, project_id: uuid.UUID,
                      job_id: uuid.UUID, output_request_id: uuid.UUID,
                      context_snapshot_id: uuid.UUID, actor_id: uuid.UUID,
                      reason: str) -> OutputJobCancelResult:
        session=self._session(transaction)
        job=session.scalar(select(JobRow).where(JobRow.job_id==job_id)
            .with_for_update(of=JobRow).execution_options(populate_existing=True))
        if (job is None or (job.owner_module,job.job_type,job.scope,job.project_id)
                != ("output","OUTPUT_GENERATE","PROJECT",project_id)
                or job.payload_refs != {"output_request_id":str(output_request_id),
                                        "context_snapshot_id":str(context_snapshot_id)}
                or job.idempotency_key != str(output_request_id)):
            raise OutputJobCancelError("RESOURCE_NOT_FOUND")
        history=(job.cancel_requested_by,job.cancel_reason,job.cancel_requested_at)
        if job.state in {"SUCCEEDED","FAILED"}:
            if any(v is not None for v in history):
                raise OutputJobCancelError("CONFLICT_STATE")
            return OutputJobCancelResult(job_id,job.state,False)
        if job.state in {"CANCEL_REQUESTED","CANCELLED"}:
            if any(v is None for v in history):
                raise OutputJobCancelError("CONFLICT_STATE")
            return OutputJobCancelResult(job_id,job.state,False)
        if job.state not in {"PENDING","RETRY_WAIT","RUNNING"} or any(v is not None for v in history):
            raise OutputJobCancelError("CONFLICT_STATE")
        now=session.execute(select(func.clock_timestamp())).scalar_one()
        if job.state=="RUNNING":
            lease=session.scalar(select(JobLeaseRow).where(
                JobLeaseRow.job_id==job_id,JobLeaseRow.fencing_token==job.fencing_token,
                JobLeaseRow.state=="ACTIVE").with_for_update(of=JobLeaseRow))
            attempt=session.scalar(select(JobAttemptRow).where(
                JobAttemptRow.job_id==job_id,JobAttemptRow.fencing_token==job.fencing_token)
                .with_for_update(of=JobAttemptRow))
            if (lease is None or attempt is None or lease.lease_expires_at<=now
                    or job.lease_expires_at!=lease.lease_expires_at
                    or attempt.worker_ref!=lease.worker_ref
                    or attempt.attempt_no!=job.attempt_count
                    or attempt.completed_at is not None or attempt.error_code is not None
                    or job.completed_at is not None):
                raise OutputJobCancelError("CONFLICT_STATE")
            job.cancel_requested_by=actor_id
            job.cancel_reason=reason
            job.cancel_requested_at=now
            job.state="CANCEL_REQUESTED"
            session.flush()
            return OutputJobCancelResult(job_id,"CANCEL_REQUESTED",True)
        active=session.scalar(select(JobLeaseRow.lease_id).where(
            JobLeaseRow.job_id==job_id,JobLeaseRow.state=="ACTIVE")
            .with_for_update(of=JobLeaseRow))
        if active is not None or job.lease_expires_at is not None or job.completed_at is not None:
            raise OutputJobCancelError("CONFLICT_STATE")
        job.cancel_requested_by=actor_id
        job.cancel_reason=reason
        job.cancel_requested_at=now
        job.state="CANCEL_REQUESTED"
        session.flush()
        job.state="CANCELLED"
        job.completed_at=now
        session.flush()
        return OutputJobCancelResult(job_id,"CANCELLED",True)
    @staticmethod
    def _session(transaction: object) -> Session:
        try: session=transaction.session
        except (AttributeError,RuntimeError): raise OutputJobCancelError() from None
        if not isinstance(session,Session) or not session.in_transaction():
            raise OutputJobCancelError()
        return session
