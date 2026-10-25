"""Non-locking one-row Parser cancel expiry hint, ordered for bounded sweeps."""

from __future__ import annotations

from sqlalchemy import and_, or_, select

from plm_assistant.modules.jobs.application.parse_cancel_scan import (
    ExpiredParserCancelCandidate, ExpiredParserCancelCursor,
)
from .lease_repository import SqlAlchemyJobLeaseRepository
from .orm import JobAttemptRow, JobLeaseRow, JobRow


class SqlAlchemyParserCancelScanRepository:
    def scan_next(self, tx, *, after=None):
        session = SqlAlchemyJobLeaseRepository._session(tx)
        now = SqlAlchemyJobLeaseRepository._now(session)
        statement = (select(JobRow.job_id, JobRow.fencing_token,
                            JobLeaseRow.worker_ref, JobLeaseRow.lease_expires_at)
            .join(JobLeaseRow, and_(JobLeaseRow.job_id == JobRow.job_id,
                                    JobLeaseRow.fencing_token == JobRow.fencing_token))
            .join(JobAttemptRow, and_(JobAttemptRow.job_id == JobRow.job_id,
                                      JobAttemptRow.fencing_token == JobRow.fencing_token))
            .where(JobRow.owner_module == "document",
                   JobRow.job_type == "DOCUMENT_PARSE", JobRow.scope == "PROJECT",
                   JobRow.state == "CANCEL_REQUESTED",
                   JobRow.completed_at.is_(None), JobRow.cancel_requested_by.is_not(None),
                   JobRow.cancel_reason.is_not(None),
                   JobRow.cancel_requested_at.is_not(None),
                   JobRow.cancel_requested_at >= JobLeaseRow.acquired_at,
                   JobRow.attempt_count >= 1, JobRow.attempt_count <= 3,
                   JobRow.attempt_count <= JobRow.max_attempts,
                   JobLeaseRow.state == "ACTIVE",
                   JobLeaseRow.lease_expires_at == JobRow.lease_expires_at,
                   JobLeaseRow.lease_expires_at <= now,
                   JobAttemptRow.attempt_no == JobRow.attempt_count,
                   JobAttemptRow.worker_ref == JobLeaseRow.worker_ref,
                   JobAttemptRow.completed_at.is_(None),
                   JobAttemptRow.error_code.is_(None)))
        if after is not None:
            statement = statement.where(or_(
                JobLeaseRow.lease_expires_at > after.expired_at,
                and_(JobLeaseRow.lease_expires_at == after.expired_at,
                     JobRow.job_id > after.job_id)))
        row = session.execute(statement.order_by(
            JobLeaseRow.lease_expires_at, JobRow.job_id).limit(1)).one_or_none()
        if row is None:
            return None
        return ExpiredParserCancelCandidate(
            ExpiredParserCancelCursor(row.lease_expires_at, row.job_id),
            row.fencing_token, row.worker_ref)
