"""Auth-owned immutable first state snapshot and explicit safe/private columns."""
from uuid import uuid4
from sqlalchemy import select,insert
from .user_repository import _session
from .user_orm import UserStateResultRow as Row
from ..application.user_read import UserReadView,_id
from ..application.user_state import UserStateError
from ..application.user_state_result import UserStateResult


class SqlAlchemyUserStateResultRepository:
    def get(self,tx,*,result_id):
        if not _id(result_id):raise UserStateError()
        row=_session(tx).execute(select(Row.user_id,Row.username_display,Row.account_state,
            Row.deployment_role,Row.credential_version,Row.created_at,Row.updated_at,Row.lock_version,
            Row.result_id,Row.actor_id,Row.audit_event_id,Row.trace_id,Row.operation,
            Row.expected_version,Row.revoked_session_count,Row.accepted_at).where(Row.result_id==result_id)).one_or_none()
        if row is None:return None
        return UserStateResult(row[8],UserReadView(*row[:8]),*row[9:])

    def record(self,tx,*,view,actor_id,audit_event_id,trace_id,operation,expected_version,revoked_session_count):
        if type(view) is not UserReadView:raise UserStateError()
        view.__post_init__()
        result_id=uuid4()
        _session(tx).execute(insert(Row).values(result_id=result_id,user_id=view.user_id,
            actor_id=actor_id,audit_event_id=audit_event_id,trace_id=trace_id,operation=operation,
            expected_version=expected_version,revoked_session_count=revoked_session_count,
            username_display=view.username_display,account_state=view.account_state,
            deployment_role=view.deployment_role,credential_version=view.credential_version,
            lock_version=view.lock_version,created_at=view.created_at,updated_at=view.updated_at))
        result=self.get(tx,result_id=result_id)
        if result is None:raise UserStateError()
        return result
