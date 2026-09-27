"""Normal current Admin proof and exact intentional first self-reset final check."""
import hashlib
import hmac
from sqlalchemy import select,func
from .user_repository import _session
from .user_orm import UserRow,PasswordCredentialRow as Credential
from .session_orm import SessionRow
from .user_state_repository import _COLUMNS
from .user_state_access import SqlAlchemyUserStateAccess
from .password_reset_result_repository import SqlAlchemyPasswordResetResults
from ..application.user_state import UserStateActorProof
from ..application.password_reset_result import PasswordResetResult
from ..application.user_read import UserReadView,_id,_time


class PasswordResetAccessError(RuntimeError):
    def __init__(self):super().__init__('AUTH_PASSWORD_RESET_ACCESS_UNAVAILABLE')


class SqlAlchemyPasswordResetAccess(SqlAlchemyUserStateAccess):
    def __init__(self,*,verifier):
        if verifier is None:raise ValueError('Actual password verifier required')
        self._verifier=verifier

    @staticmethod
    def _inputs(token,csrf,now):
        return all(type(v) is bytes and len(v)==32 for v in (token,csrf)) and _time(now)

    def prove(self,tx,*,session_token,csrf_token,now):
        if not self._inputs(session_token,csrf_token,now):return None
        try:return super().prove(tx,session_token=session_token,csrf_token=csrf_token,now=now)
        except Exception:raise PasswordResetAccessError() from None

    def require_self_reset(self,tx,*,proof,result,session_token,csrf_token,trace_id,expected_version,now):
        if (not self._inputs(session_token,csrf_token,now) or not _id(trace_id)
            or type(expected_version) is not int or not 0<=expected_version<9223372036854775807):return False
        try:
            if type(proof) is not UserStateActorProof or type(result) is not PasswordResetResult:return False
            proof.__post_init__();result.__post_init__();old=proof.user_view
            if (result.user_id!=old.user_id or result.actor_id!=old.user_id or result.target_state!='ENABLED'
                or result.trace_id!=trace_id or result.before_credential_id!=proof.credential_id
                or result.before_credential_version!=old.credential_version or expected_version!=old.lock_version
                or result.before_user_version!=expected_version or result.revoked_session_count<1
                or SqlAlchemyPasswordResetResults(verifier=self._verifier).get(tx,result_id=result.result_id)!=result):return False
            before_flag=_session(tx).execute(select(Credential.must_change_password).where(
                Credential.password_credential_id==proof.credential_id,Credential.user_id==old.user_id,
                Credential.credential_version==old.credential_version)).scalar_one_or_none()
            if before_flag is not False:return False
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
            if (current.account_state!='ENABLED' or current.deployment_role!='DEPLOYMENT_ADMIN'
                or current.credential_version!=result.credential_version or current.lock_version!=result.user_version
                or current.updated_at!=result.changed_at or current.updated_at<old.updated_at
                or any(getattr(current,k)!=getattr(old,k) for k in ('user_id','username_display','deployment_role','created_at'))
                or row[8]!=result.credential_id or row[9]!=old.user_id or row[10] is not True or row[11]!=old.user_id
                or row[12]!=old.credential_version or row[13]!=proof.session_version+1
                or row[14]!=proof.session_created_at or row[15]!=proof.session_idle_expires_at or row[16]!=proof.session_absolute_expires_at
                or not row[14]<=now<row[15] or not now<row[16] or row[17]!=result.changed_at or row[18]!='PASSWORD_RESET'
                or not hmac.compare_digest(row[19],hashlib.sha256(csrf_token).digest())):return False
            session=_session(tx)
            if session.execute(select(SessionRow.session_id).where(SessionRow.user_id==old.user_id,
                SessionRow.revoked_at.is_(None)).limit(1)).first() is not None:return False
            count=session.execute(select(func.count()).select_from(SessionRow).where(SessionRow.user_id==old.user_id,
                SessionRow.revoked_at==result.changed_at,SessionRow.revoke_reason=='PASSWORD_RESET')).scalar_one()
            return type(count) is int and count==result.revoked_session_count
        except Exception:raise PasswordResetAccessError() from None
