"""Actual Auth-owned locked enabled User lookup, only for trusted async callers."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from .user_orm import UserRow


class SqlAlchemyCurrentUserAccess:
    def current_enabled_user(self, transaction: object, *, user_id: UUID):
        if type(user_id) is not UUID or not user_id.int:
            raise ValueError("invalid User identity")
        session = transaction.session
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Auth transaction required")
        row = session.execute(select(UserRow.user_id, UserRow.deployment_role).where(
            UserRow.user_id == user_id, UserRow.state == "ENABLED",
        ).with_for_update(of=UserRow)).one_or_none()
        return None if row is None else CurrentUserFacts(row.user_id, row.deployment_role)
