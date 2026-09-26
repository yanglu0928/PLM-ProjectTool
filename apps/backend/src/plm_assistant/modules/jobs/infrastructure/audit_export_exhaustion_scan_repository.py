"""Owned non-locking one-candidate scan, no Audit root or terminal mutations."""
from uuid import UUID
from sqlalchemy import select
from ..application.audit_export_exhaustion_scan import AuditExportExhaustionCandidate
from ..application.lease import JobLeaseError
from .lease_repository import SqlAlchemyJobLeaseRepository
from .orm import JobRow,JobLeaseRow,JobAttemptRow


class SqlAlchemyAuditExportExhaustionScanRepository:
    def peek_next(self,tx):
        leases=SqlAlchemyJobLeaseRepository();session=leases._session(tx);now=leases._now(session)
        row=session.execute(select(JobRow.job_id,JobRow.payload_refs,JobRow.fencing_token,JobLeaseRow.worker_ref)
            .join(JobLeaseRow,(JobLeaseRow.job_id==JobRow.job_id)&(JobLeaseRow.fencing_token==JobRow.fencing_token))
            .join(JobAttemptRow,(JobAttemptRow.job_id==JobRow.job_id)&(JobAttemptRow.fencing_token==JobRow.fencing_token))
            .where(JobRow.owner_module=='audit',JobRow.job_type=='AUDIT_EXPORT',JobRow.state=='RUNNING',
                JobRow.max_attempts==3,JobRow.attempt_count==3,JobRow.completed_at.is_(None),
                JobLeaseRow.state=='ACTIVE',JobLeaseRow.lease_expires_at==JobRow.lease_expires_at,
                JobLeaseRow.lease_expires_at<=now,JobAttemptRow.attempt_no==3,
                JobAttemptRow.worker_ref==JobLeaseRow.worker_ref,JobAttemptRow.completed_at.is_(None),JobAttemptRow.error_code.is_(None))
            .order_by(JobLeaseRow.lease_expires_at,JobRow.job_id).limit(1)).one_or_none()
        if row is None:return None
        raw=row.payload_refs.get('export_id') if type(row.payload_refs) is dict else None
        try:
            if type(raw) is not str:raise ValueError()
            export=UUID(raw)
            if str(export)!=raw:raise ValueError()
            return AuditExportExhaustionCandidate(row.job_id,export,row.fencing_token,row.worker_ref)
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
