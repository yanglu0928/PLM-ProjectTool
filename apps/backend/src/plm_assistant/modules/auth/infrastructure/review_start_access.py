"""Session/CSRF proof with shared User locks, before reviewer/project locks."""
import hashlib
import hmac
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from .user_orm import UserRow
from .session_orm import SessionRow


class SqlAlchemyReviewStartAccess:
    def authenticated_user(self, tx, *, session_token, csrf_token, now):
        if (any(type(v) is not bytes or len(v)!=32 for v in (session_token,csrf_token))
                or type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None):
            return None
        session = getattr(tx,"session",None)
        if not isinstance(session,Session) or not session.in_transaction():
            raise RuntimeError("active Review authentication transaction required")
        row = session.execute(select(SessionRow.user_id,SessionRow.csrf_digest).join(UserRow,SessionRow.user_id==UserRow.user_id).where(
            SessionRow.session_token_digest==hashlib.sha256(session_token).digest(), SessionRow.revoked_at.is_(None),
            SessionRow.created_at<=now,SessionRow.idle_expires_at>now,SessionRow.absolute_expires_at>now,
            UserRow.state=="ENABLED",UserRow.credential_version==SessionRow.credential_version
        ).with_for_update(read=True,of=(SessionRow,UserRow))).one_or_none()
        return None if row is None or not hmac.compare_digest(bytes(row.csrf_digest),hashlib.sha256(csrf_token).digest()) else row.user_id
