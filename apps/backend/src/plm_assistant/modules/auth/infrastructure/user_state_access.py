"""Actual current Admin proof and narrow intentional self-disable final check."""
import hashlib
import hmac
from sqlalchemy import select,text
from .license_import_access import SqlAlchemyLicenseImportAccess
from .user_repository import _session
from .user_orm import UserRow
from .session_orm import SessionRow
from .user_state_repository import _COLUMNS
from ..application.user_read import UserReadView
from ..application.user_state import UserStateActorProof,UserStateError


class SqlAlchemyUserStateAccess(SqlAlchemyLicenseImportAccess):
    def lock_deployment(self,tx):
        session=_session(tx)
        session.execute(text("SELECT set_config('lock_timeout','5000ms',true)"))
        session.execute(text('SELECT pg_advisory_xact_lock(1347177793,1431524436)'))
        return True

    def prove(self,tx,*,session_token,csrf_token,now):
        actor=self.authorized_admin(tx,session_token=session_token,csrf_token=csrf_token,now=now)
        if actor is None:return None
        row=_session(tx).execute(select(*_COLUMNS,UserRow.active_password_credential_id,
            SessionRow.session_id,SessionRow.lock_version,SessionRow.created_at,
            SessionRow.idle_expires_at,SessionRow.absolute_expires_at).join(
            SessionRow,SessionRow.user_id==UserRow.user_id).where(UserRow.user_id==actor,
                SessionRow.session_token_digest==hashlib.sha256(session_token).digest())
            .with_for_update(of=(UserRow,SessionRow))).one_or_none()
        if row is None:raise UserStateError()
        return UserStateActorProof(UserReadView(*row[:8]),*row[8:])

    def require_self_disabled(self,tx,*,proof,command,result,now):
        # This is not a generic authentication bypass. Verify the exact locked
        # pre-mutation identity and only the expected own-command differences.
        proof.__post_init__();result.__post_init__()
        if (result.operation!='DISABLE' or proof.user_view.user_id!=command.user_id
            or result.actor_id!=command.user_id or result.revoked_session_count<1
            or command.expected_version!=proof.user_view.lock_version
            or result.expected_version!=command.expected_version or result.trace_id!=command.trace_id
            or result.first_view.user_id!=command.user_id):return False
        row=_session(tx).execute(select(*_COLUMNS,UserRow.active_password_credential_id,
            UserRow.updated_by,SessionRow.user_id,SessionRow.credential_version,SessionRow.lock_version,
            SessionRow.created_at,SessionRow.idle_expires_at,SessionRow.absolute_expires_at,
            SessionRow.revoked_at,SessionRow.revoke_reason,SessionRow.csrf_digest).join(
            SessionRow,SessionRow.user_id==UserRow.user_id).where(UserRow.user_id==command.user_id,
            SessionRow.session_id==proof.session_id,
            SessionRow.session_token_digest==hashlib.sha256(command.session_token).digest())
            .with_for_update(of=(UserRow,SessionRow))).one_or_none()
        if row is None:return False
        current=UserReadView(*row[:8]);old=proof.user_view
        if (current!=result.first_view or current.account_state!='DISABLED'
            or current.lock_version!=old.lock_version+1 or current.updated_at<old.updated_at
            or any(getattr(current,k)!=getattr(old,k) for k in
                   ('user_id','username_display','deployment_role','credential_version','created_at'))
            or row[8]!=proof.credential_id or row[9]!=old.user_id or row[10]!=old.user_id
            or row[11]!=old.credential_version or row[12]!=proof.session_version+1
            or row[13]!=proof.session_created_at or row[14]!=proof.session_idle_expires_at
            or row[15]!=proof.session_absolute_expires_at
            or not row[13]<=now<row[14] or not now<row[15]
            or row[16]!=current.updated_at or row[17]!='USER_DISABLED'
            or not hmac.compare_digest(row[18],hashlib.sha256(command.csrf_token).digest())):return False
        session=_session(tx)
        if session.execute(select(SessionRow.session_id).where(SessionRow.user_id==old.user_id,
            SessionRow.revoked_at.is_(None)).limit(1)).first() is not None:return False
        return session.execute(select(UserRow.user_id).where(UserRow.user_id!=old.user_id,
            UserRow.state=='ENABLED',UserRow.deployment_role=='DEPLOYMENT_ADMIN').limit(1)
            .with_for_update(read=True,of=UserRow)).first() is not None
