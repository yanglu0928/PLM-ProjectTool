"""Auth-owned current User eligibility for Project membership creation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyProjectMemberCreateAccess(SqlAlchemyProjectWriteAccess):
    def lock_eligible_member(self, transaction: object, user_id: uuid.UUID) -> str | None:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Auth transaction is required")
        return session.execute(select(UserRow.username_display).where(
            UserRow.user_id == user_id,
            UserRow.state == "ENABLED",
        ).with_for_update(of=UserRow)).scalar_one_or_none()
