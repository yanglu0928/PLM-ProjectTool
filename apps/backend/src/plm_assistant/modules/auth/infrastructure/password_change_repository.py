"""Append normal Credential, advance current User and revoke every outstanding Session."""
from sqlalchemy import select,insert,update,func
from .user_repository import _session
from .user_orm import UserRow,PasswordCredentialRow
from .session_orm import SessionRow
from .user_create_result_repository import SqlAlchemyUserCreateResultRepository
from ..application.password_change import PasswordChangeError
from ..application.password_change_actor import PasswordChangeActorProof
from ..application.ports.password_hash import PasswordHashResult
from ..application.user_read import UserReadView
from .user_state_repository import _COLUMNS


class SqlAlchemyPasswordChangeRepository:
    def change(self,tx,*,proof,password_hash):
        if type(proof) is not PasswordChangeActorProof or type(password_hash) is not PasswordHashResult:
            raise PasswordChangeError()
        proof.__post_init__()
        SqlAlchemyUserCreateResultRepository._validate_hash(password_hash.password_hash,
            password_hash.algorithm_id,dict(password_hash.parameter_set))
        before=proof.user_view
        if before.credential_version>=9223372036854775807 or before.lock_version>=9223372036854775807:
            raise PasswordChangeError()
        session=_session(tx)
        row=session.execute(select(*_COLUMNS,UserRow.active_password_credential_id)
            .where(UserRow.user_id==before.user_id).with_for_update(of=UserRow)).one_or_none()
        if row is None or UserReadView(*row[:8])!=before or row[8]!=proof.credential_id:
            raise PasswordChangeError('AUTH_ACCESS_DENIED')
        credential_id=session.execute(insert(PasswordCredentialRow).values(user_id=before.user_id,
            credential_version=before.credential_version+1,password_hash=password_hash.password_hash,
            algorithm_id=password_hash.algorithm_id,parameter_set=dict(password_hash.parameter_set),
            must_change_password=False,changed_by=before.user_id)
            .returning(PasswordCredentialRow.password_credential_id)).scalar_one()
        after=session.execute(update(UserRow).where(UserRow.user_id==before.user_id,
            UserRow.lock_version==before.lock_version,UserRow.active_password_credential_id==proof.credential_id,
            UserRow.credential_version==before.credential_version,UserRow.state=='ENABLED').values(
            active_password_credential_id=credential_id,credential_version=before.credential_version+1,
            lock_version=before.lock_version+1,updated_by=before.user_id,updated_at=func.statement_timestamp())
            .returning(*_COLUMNS)).one_or_none()
        if after is None:raise PasswordChangeError('AUTH_ACCESS_DENIED')
        view=UserReadView(*after)
        if view.updated_at<before.updated_at or any(getattr(view,k)!=getattr(before,k) for k in (
            'user_id','username_display','account_state','deployment_role','created_at')):raise PasswordChangeError()
        count=session.execute(update(SessionRow).where(SessionRow.user_id==before.user_id,
            SessionRow.revoked_at.is_(None)).values(revoked_at=view.updated_at,revoke_reason='PASSWORD_CHANGED',
            lock_version=SessionRow.lock_version+1)).rowcount
        if type(count) is not int or not 1<=count<=9223372036854775807:raise PasswordChangeError()
        return credential_id,view.updated_at,count
