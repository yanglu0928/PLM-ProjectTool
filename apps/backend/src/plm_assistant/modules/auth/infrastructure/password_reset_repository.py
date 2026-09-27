"""Append temporary Credential and revoke all outstanding Sessions in caller UOW."""
from sqlalchemy import select,insert,update,func
from .user_repository import _session
from .user_orm import UserRow,PasswordCredentialRow
from .session_orm import SessionRow
from .user_state_repository import _COLUMNS
from .user_create_result_repository import SqlAlchemyUserCreateResultRepository
from ..application.password_reset import PasswordResetError
from ..application.ports.password_hash import PasswordHashResult
from ..application.user_read import UserReadView,_id


class SqlAlchemyPasswordResetRepository:
    def reset(self,tx,*,user_id,expected_version,actor_id,password_hash):
        if (not _id(user_id) or not _id(actor_id) or type(expected_version) is not int
            or not 0<=expected_version<9223372036854775807 or type(password_hash) is not PasswordHashResult):
            raise PasswordResetError('VALIDATION_FAILED')
        SqlAlchemyUserCreateResultRepository._validate_hash(password_hash.password_hash,password_hash.algorithm_id,
            dict(password_hash.parameter_set))
        session=_session(tx)
        row=session.execute(select(*_COLUMNS,UserRow.active_password_credential_id).where(
            UserRow.user_id==user_id).with_for_update(of=UserRow)).one_or_none()
        if row is None:raise PasswordResetError('RESOURCE_NOT_FOUND')
        before=UserReadView(*row[:8]);oldid=row[8]
        if before.lock_version!=expected_version:raise PasswordResetError('CONFLICT_VERSION')
        if not _id(oldid) or not 1<=before.credential_version<9223372036854775807:raise PasswordResetError()
        newid=session.execute(insert(PasswordCredentialRow).values(user_id=user_id,credential_version=before.credential_version+1,
            password_hash=password_hash.password_hash,algorithm_id=password_hash.algorithm_id,
            parameter_set=dict(password_hash.parameter_set),must_change_password=True,changed_by=actor_id)
            .returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        after=session.execute(update(UserRow).where(UserRow.user_id==user_id,UserRow.lock_version==expected_version,
            UserRow.active_password_credential_id==oldid,UserRow.credential_version==before.credential_version,
            UserRow.state==before.account_state).values(active_password_credential_id=newid,
            credential_version=before.credential_version+1,lock_version=before.lock_version+1,updated_by=actor_id,
            updated_at=func.statement_timestamp()).returning(*_COLUMNS)).one_or_none()
        if after is None:raise PasswordResetError('CONFLICT_VERSION')
        view=UserReadView(*after)
        if view.updated_at<before.updated_at or any(getattr(view,k)!=getattr(before,k) for k in (
            'user_id','username_display','account_state','deployment_role','created_at')):raise PasswordResetError()
        count=session.execute(update(SessionRow).where(SessionRow.user_id==user_id,SessionRow.revoked_at.is_(None))
            .values(revoked_at=view.updated_at,revoke_reason='PASSWORD_RESET',lock_version=SessionRow.lock_version+1)).rowcount
        if type(count) is not int or not 0<=count<=9223372036854775807:raise PasswordResetError()
        return view,oldid,before,count,newid
