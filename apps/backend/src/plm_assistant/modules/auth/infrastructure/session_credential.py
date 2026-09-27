"""Auth-owned exact active credential source, no stored Session permission flag."""
import hashlib
from datetime import datetime
from sqlalchemy import select, exists
from .user_repository import _session
from .user_orm import UserRow, PasswordCredentialRow
from .session_orm import SessionRow
from ..application.session_credential import SessionCredentialFact


def normal_current_credential():
    return exists(select(PasswordCredentialRow.password_credential_id).where(
        PasswordCredentialRow.password_credential_id==UserRow.active_password_credential_id,
        PasswordCredentialRow.user_id==UserRow.user_id,
        PasswordCredentialRow.credential_version==UserRow.credential_version,
        PasswordCredentialRow.must_change_password.is_(False))).correlate(UserRow)


class SqlAlchemySessionCredentialFacts:
    def get(self, transaction, *, session_token, now):
        if (type(session_token) is not bytes or len(session_token)!=32 or type(now) is not datetime
            or now.tzinfo is None or now.utcoffset() is None):
            return None
        row=_session(transaction).execute(select(UserRow.user_id,SessionRow.session_id,
            PasswordCredentialRow.password_credential_id,UserRow.credential_version,
            PasswordCredentialRow.must_change_password).select_from(SessionRow)
            .join(UserRow,UserRow.user_id==SessionRow.user_id)
            .join(PasswordCredentialRow,
                PasswordCredentialRow.password_credential_id==UserRow.active_password_credential_id)
            .where(SessionRow.session_token_digest==hashlib.sha256(session_token).digest(),
                SessionRow.revoked_at.is_(None),SessionRow.created_at<=now,
                SessionRow.idle_expires_at>now,SessionRow.absolute_expires_at>now,
                UserRow.state=='ENABLED',UserRow.credential_version==SessionRow.credential_version,
                PasswordCredentialRow.user_id==UserRow.user_id,
                PasswordCredentialRow.credential_version==UserRow.credential_version)
            .with_for_update(read=True,of=(UserRow,SessionRow))).one_or_none()
        return None if row is None else SessionCredentialFact(*row)
