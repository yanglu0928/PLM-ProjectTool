"""Owned non-locking one-candidate scan, no Audit root or terminal mutations."""
from uuid import UUID
from sqlalchemy import select,and_,or_
from ..application.audit_export_exhaustion_scan import AuditExportExhaustionCandidate,AuditExportExhaustionCursor,AuditExportExhaustionScan
from ..application.lease import JobLeaseError
from .lease_repository import SqlAlchemyJobLeaseRepository
from .orm import JobRow,JobLeaseRow,JobAttemptRow


class SqlAlchemyAuditExportExhaustionScanRepository:
    def peek_next(self,tx):
        row=self._next_row(tx)
        if row is None:return None
        return self._candidate(row)

    def _next_row(self,tx,after=None):
        leases=SqlAlchemyJobLeaseRepository();session=leases._session(tx);now=leases._now(session)
        statement=(select(JobRow.job_id,JobRow.payload_refs,JobRow.fencing_token,JobLeaseRow.worker_ref,JobLeaseRow.lease_expires_at)
            .join(JobLeaseRow,(JobLeaseRow.job_id==JobRow.job_id)&(JobLeaseRow.fencing_token==JobRow.fencing_token))
            .join(JobAttemptRow,(JobAttemptRow.job_id==JobRow.job_id)&(JobAttemptRow.fencing_token==JobRow.fencing_token))
            .where(JobRow.owner_module=='audit',JobRow.job_type=='AUDIT_EXPORT',JobRow.state=='RUNNING',
                JobRow.max_attempts==3,JobRow.attempt_count==3,JobRow.completed_at.is_(None),
                JobLeaseRow.state=='ACTIVE',JobLeaseRow.lease_expires_at==JobRow.lease_expires_at,
                JobLeaseRow.lease_expires_at<=now,JobAttemptRow.attempt_no==3,
                JobAttemptRow.worker_ref==JobLeaseRow.worker_ref,JobAttemptRow.completed_at.is_(None),JobAttemptRow.error_code.is_(None)))
        if after is not None:
            statement=statement.where(or_(JobLeaseRow.lease_expires_at>after.expired_at,
                and_(JobLeaseRow.lease_expires_at==after.expired_at,JobRow.job_id>after.job_id)))
        return session.execute(statement.order_by(JobLeaseRow.lease_expires_at,JobRow.job_id).limit(1)).one_or_none()

    @staticmethod
    def _candidate(row):
        raw=row.payload_refs.get('export_id') if type(row.payload_refs) is dict else None
        try:
            if type(raw) is not str:raise ValueError()
            export=UUID(raw)
            if str(export)!=raw:raise ValueError()
            return AuditExportExhaustionCandidate(row.job_id,export,row.fencing_token,row.worker_ref)
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def scan_next(self,tx,*,after=None):
        if after is not None:
            if type(after) is not AuditExportExhaustionCursor:raise JobLeaseError('VALIDATION_FAILED')
            after.__post_init__()
        row=self._next_row(tx,after)
        if row is None:return None
        cursor=AuditExportExhaustionCursor(row.lease_expires_at,row.job_id)
        raw=row.payload_refs.get('export_id') if type(row.payload_refs) is dict else None
        try:
            if type(raw) is not str:raise ValueError()
            export=UUID(raw)
            if not export.int or str(export)!=raw:raise ValueError()
        except ValueError:return AuditExportExhaustionScan(cursor,None,'INVALID_EXPORT_REF')
        return AuditExportExhaustionScan(cursor,self._candidate(row))
