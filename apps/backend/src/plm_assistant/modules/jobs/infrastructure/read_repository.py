"""Jobs-only columns; no mutation, raw payload or Lease exposure."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..application.authorized_read import JobReadFacts,JobReadError,_id
from .orm import JobRow

class SqlAlchemyJobReadRepository:
    def get(self,tx,*,job_id):
        if not _id(job_id):raise JobReadError('VALIDATION_FAILED')
        session=tx.session
        if not isinstance(session,Session) or not session.in_transaction():raise JobReadError()
        row=session.execute(select(JobRow.job_id,JobRow.owner_module,JobRow.job_type,JobRow.scope,JobRow.project_id,
            JobRow.actor_ref.label('actor_id'),JobRow.state,JobRow.attempt_count,JobRow.created_at,JobRow.completed_at,JobRow.lock_version)
            .where(JobRow.job_id==job_id)).mappings().one_or_none()
        return None if row is None else JobReadFacts(**dict(row))
