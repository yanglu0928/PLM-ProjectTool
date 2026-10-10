"""Auth-owned enabled reviewer IDs under shared locks; no identity metadata."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from .user_orm import UserRow


class SqlAlchemyReviewUserAccess:
    def lock_enabled_users(self, tx, user_ids):
        if (type(user_ids) is not tuple or not user_ids or any(type(v) is not UUID or not v.int for v in user_ids)
                or user_ids != tuple(sorted(set(user_ids)))):
            raise ValueError("validated sorted reviewer identities required")
        session = getattr(tx, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active reviewer qualification transaction required")
        return tuple(session.execute(select(UserRow.user_id).where(UserRow.user_id.in_(user_ids),
            UserRow.state == "ENABLED").order_by(UserRow.user_id).with_for_update(read=True, of=UserRow)).scalars())
