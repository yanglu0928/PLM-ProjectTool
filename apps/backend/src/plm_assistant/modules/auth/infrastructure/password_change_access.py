"""Real current own identity/CSRF and narrow intentional change final proof."""
import hashlib
import hmac
from sqlalchemy import select,func
from .user_repository import _session
from .user_orm import UserRow,PasswordCredentialRow as Credential
from .session_orm import SessionRow
from .user_state_repository import _COLUMNS
from .user_state_access import SqlAlchemyUserStateAccess
from .user_create_result_repository import SqlAlchemyUserCreateResultRepository
from .password_change_result_repository import SqlAlchemyPasswordChangeResults
from ..application.user_read import UserReadView,_time,_id
from ..application.password_change_actor import PasswordChangeActorProof
from ..application.password_change_result import PasswordChangeResult


class PasswordChangeAccessError(RuntimeError):
    def __init__(self):super().__init__('AUTH_PASSWORD_ACCESS_UNAVAILABLE')


class SqlAlchemyPasswordChangeAccess:
    def __init__(self,*,verifier):
        if verifier is None:raise ValueError('Actual password verifier required')
        self._verifier=verifier

    def lock_deployment(self,tx):return SqlAlchemyUserStateAccess.lock_deployment(self,tx)

    @staticmethod
    def _inputs(token,csrf,now):
        return all(type(v) is bytes and len(v)==32 for v in (token,csrf)) and _time(now)

    def prove(self,tx,*,session_token,csrf_token,now):
        if not self._inputs(session_token,csrf_token,now):return None
        try:
            row=_session(tx).execute(select(*_COLUMNS,UserRow.active_password_credential_id,
                Credential.must_change_password,SessionRow.session_id,SessionRow.lock_version,
                SessionRow.created_at,SessionRow.idle_expires_at,SessionRow.absolute_expires_at,SessionRow.csrf_digest)
                .join(SessionRow,SessionRow.user_id==UserRow.user_id)
                .join(Credential,Credential.password_credential_id==UserRow.active_password_credential_id)
                .where(SessionRow.session_token_digest==hashlib.sha256(session_token).digest(),
                    UserRow.state=='ENABLED',UserRow.credential_version==SessionRow.credential_version,
                    Credential.user_id==UserRow.user_id,Credential.credential_version==UserRow.credential_version,
                    SessionRow.revoked_at.is_(None),SessionRow.created_at<=now,
                    SessionRow.idle_expires_at>now,SessionRow.absolute_expires_at>now)
                .with_for_update(of=(UserRow,SessionRow))).one_or_none()
            if row is None or not hmac.compare_digest(row[-1],hashlib.sha256(csrf_token).digest()):return None
            return PasswordChangeActorProof(UserReadView(*row[:8]),*row[8:-1])
        except Exception:raise PasswordChangeAccessError() from None

    def verify_current_password(self,tx,*,proof,password):
        try:
            if type(proof) is not PasswordChangeActorProof or type(password) is not memoryview or not 1<=len(password)<=1024:
                raise PasswordChangeAccessError()
            proof.__post_init__()
            row=_session(tx).execute(select(Credential.password_hash,Credential.algorithm_id,Credential.parameter_set)
                .join(UserRow,UserRow.active_password_credential_id==Credential.password_credential_id)
                .where(UserRow.user_id==proof.user_view.user_id,UserRow.state=='ENABLED',
                    UserRow.lock_version==proof.user_view.lock_version,Credential.user_id==UserRow.user_id,
                    Credential.password_credential_id==proof.credential_id,
                    Credential.credential_version==proof.user_view.credential_version,
                    Credential.must_change_password==proof.password_change_required)).one_or_none()
            if row is None:raise PasswordChangeAccessError()
            SqlAlchemyUserCreateResultRepository._validate_hash(row.password_hash,row.algorithm_id,row.parameter_set)
            matched=self._verifier.verify_password(password,password_hash=row.password_hash,
                algorithm_id=row.algorithm_id,parameter_set=row.parameter_set)
            if type(matched) is not bool:raise PasswordChangeAccessError()
            return matched
        except Exception:raise PasswordChangeAccessError() from None

    def require_changed(self,tx,*,proof,result,session_token,csrf_token,trace_id,now):
        if not self._inputs(session_token,csrf_token,now) or not _id(trace_id):return False
        try:
            if type(proof) is not PasswordChangeActorProof or type(result) is not PasswordChangeResult:return False
            proof.__post_init__();result.__post_init__();old=proof.user_view
            if (result.user_id!=old.user_id or result.trace_id!=trace_id or result.before_credential_id!=proof.credential_id
                or result.before_credential_version!=old.credential_version or result.before_user_version!=old.lock_version
                or SqlAlchemyPasswordChangeResults(verifier=self._verifier).get(tx,result_id=result.result_id)!=result):return False
            before_flag=_session(tx).execute(select(Credential.must_change_password).where(
                Credential.password_credential_id==proof.credential_id,Credential.user_id==old.user_id,
                Credential.credential_version==old.credential_version)).scalar_one_or_none()
            if type(before_flag) is not bool or before_flag!=proof.password_change_required:return False
            row=_session(tx).execute(select(*_COLUMNS,UserRow.active_password_credential_id,UserRow.updated_by,
                Credential.must_change_password,Credential.changed_by,SessionRow.credential_version,SessionRow.lock_version,
                SessionRow.created_at,SessionRow.idle_expires_at,SessionRow.absolute_expires_at,
                SessionRow.revoked_at,SessionRow.revoke_reason,SessionRow.csrf_digest)
                .join(SessionRow,SessionRow.user_id==UserRow.user_id)
                .join(Credential,Credential.password_credential_id==UserRow.active_password_credential_id)
                .where(UserRow.user_id==old.user_id,SessionRow.session_id==proof.session_id,
                    SessionRow.session_token_digest==hashlib.sha256(session_token).digest(),
                    Credential.user_id==UserRow.user_id,Credential.credential_version==UserRow.credential_version)
                .with_for_update(of=(UserRow,SessionRow))).one_or_none()
            if row is None:return False
            current=UserReadView(*row[:8])
            if (current.account_state!='ENABLED' or current.credential_version!=result.credential_version
                or current.lock_version!=result.user_version or current.updated_at!=result.changed_at
                or current.updated_at<old.updated_at
                or any(getattr(current,k)!=getattr(old,k) for k in ('user_id','username_display','deployment_role','created_at'))
                or row[8]!=result.credential_id or row[9]!=old.user_id or row[10] is not False or row[11]!=old.user_id
                or row[12]!=old.credential_version or row[13]!=proof.session_version+1
                or row[14]!=proof.session_created_at or row[15]!=proof.session_idle_expires_at or row[16]!=proof.session_absolute_expires_at
                or not row[14]<=now<row[15] or not now<row[16] or row[17]!=result.changed_at or row[18]!='PASSWORD_CHANGED'
                or not hmac.compare_digest(row[19],hashlib.sha256(csrf_token).digest())):return False
            session=_session(tx)
            if session.execute(select(SessionRow.session_id).where(SessionRow.user_id==old.user_id,
                SessionRow.revoked_at.is_(None)).limit(1)).first() is not None:return False
            count=session.execute(select(func.count()).select_from(SessionRow).where(SessionRow.user_id==old.user_id,
                SessionRow.revoked_at==result.changed_at,SessionRow.revoke_reason=='PASSWORD_CHANGED')).scalar_one()
            return type(count) is int and count==result.revoked_session_count
        except Exception:raise PasswordChangeAccessError() from None
