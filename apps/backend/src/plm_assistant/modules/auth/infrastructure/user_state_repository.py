"""Caller-UOW conditional User state and all outstanding Session revocation."""
from sqlalchemy import select,update,func
from .user_repository import _session
from .user_orm import UserRow
from .session_orm import SessionRow
from ..application.user_read import UserReadView,_id
from ..application.user_state import UserStateError
from ..domain.user_state import decide_user_state

_COLUMNS=(UserRow.user_id,UserRow.username_display,UserRow.state,UserRow.deployment_role,
    UserRow.credential_version,UserRow.created_at,UserRow.updated_at,UserRow.lock_version)


class SqlAlchemyUserStateRepository:
    def change(self,tx,*,user_id,expected_version,operation,actor_id):
        if not _id(user_id) or not _id(actor_id):raise UserStateError('VALIDATION_FAILED')
        session=_session(tx)
        row=session.execute(select(*_COLUMNS,UserRow.active_password_credential_id).where(
            UserRow.user_id==user_id).with_for_update(of=UserRow)).one_or_none()
        if row is None:raise UserStateError('RESOURCE_NOT_FOUND')
        before=UserReadView(*row[:8])
        # Shared locks keep other currently enabled Admin identities available.
        admins=session.execute(select(UserRow.user_id).where(UserRow.user_id!=user_id,
            UserRow.state=='ENABLED',UserRow.deployment_role=='DEPLOYMENT_ADMIN')
            .order_by(UserRow.user_id).with_for_update(read=True,of=UserRow)).all()
        transition=decide_user_state(operation=operation,state=before.account_state,
            deployment_role=before.deployment_role,credential_version=before.credential_version,
            has_active_credential=_id(row[8]),lock_version=before.lock_version,
            expected_version=expected_version,other_enabled_admins=len(admins))
        updated=session.execute(update(UserRow).where(UserRow.user_id==user_id,
            UserRow.lock_version==expected_version,UserRow.state==transition.before_state).values(
            state=transition.after_state,lock_version=UserRow.lock_version+1,updated_by=actor_id,
            updated_at=func.statement_timestamp()).returning(*_COLUMNS)).one_or_none()
        if updated is None:raise UserStateError('CONFLICT_VERSION')
        view=UserReadView(*updated)
        if (view.updated_at<before.updated_at or any(getattr(view,k)!=getattr(before,k) for k in
            ('user_id','username_display','deployment_role','credential_version','created_at'))):raise UserStateError()
        count=0
        if transition.revoke_all_sessions:
            result=session.execute(update(SessionRow).where(SessionRow.user_id==user_id,
                SessionRow.revoked_at.is_(None)).values(revoked_at=view.updated_at,revoke_reason='USER_DISABLED',
                lock_version=SessionRow.lock_version+1))
            count=result.rowcount
            if type(count) is not int or count<0:raise UserStateError()
        return view,before.account_state,count
