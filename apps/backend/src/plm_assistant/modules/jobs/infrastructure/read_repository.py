"""Jobs-only columns; no mutation, raw payload or Lease exposure."""
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session
from ..application.authorized_read import JobReadFacts,JobReadError,_id
from .orm import JobRow
from ..application.authorized_list import JobListCandidates

class SqlAlchemyJobReadRepository:
    def list(self,tx,*,project_id,scope,actor_id,owner_types,before,limit):
        session=tx.session
        if not isinstance(session,Session) or not session.in_transaction():raise JobReadError()
        if (type(limit) is not int or not 1<=limit<=200 or type(owner_types) is not tuple or not owner_types):raise JobReadError()
        query=select(JobRow.job_id,JobRow.owner_module,JobRow.job_type,JobRow.scope,JobRow.project_id,
            JobRow.actor_ref.label('actor_id'),JobRow.state,JobRow.attempt_count,JobRow.created_at,JobRow.completed_at,JobRow.lock_version)
        query=query.where(JobRow.project_id==project_id,
            JobRow.scope.in_(('GLOBAL','DEPLOYMENT') if project_id is None else ('PROJECT',)),
            or_(*(and_(JobRow.owner_module==owner,JobRow.job_type==kind) for owner,kind in owner_types)))
        if scope is not None:query=query.where(JobRow.scope==scope)
        if actor_id is not None:query=query.where(JobRow.actor_ref==actor_id)
        if before is not None:query=query.where(or_(JobRow.created_at<before[0],and_(JobRow.created_at==before[0],JobRow.job_id<before[1])))
        rows=session.execute(query.order_by(JobRow.created_at.desc(),JobRow.job_id.desc()).limit(limit+1)).mappings().all()
        return JobListCandidates(tuple(JobReadFacts(**dict(row)) for row in rows[:limit]),len(rows)>limit)

    def get(self,tx,*,job_id):
        if not _id(job_id):raise JobReadError('VALIDATION_FAILED')
        session=tx.session
        if not isinstance(session,Session) or not session.in_transaction():raise JobReadError()
        row=session.execute(select(JobRow.job_id,JobRow.owner_module,JobRow.job_type,JobRow.scope,JobRow.project_id,
            JobRow.actor_ref.label('actor_id'),JobRow.state,JobRow.attempt_count,JobRow.created_at,JobRow.completed_at,JobRow.lock_version)
            .where(JobRow.job_id==job_id)).mappings().one_or_none()
        return None if row is None else JobReadFacts(**dict(row))
