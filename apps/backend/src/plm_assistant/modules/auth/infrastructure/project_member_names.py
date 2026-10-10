"""Auth-owned minimal display-name projection for authorized Project member pages."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyProjectMemberNames(SqlAlchemyProjectReadAccess):
    def display_names(self, transaction: object,
                      user_ids: tuple[uuid.UUID, ...]) -> dict[uuid.UUID, str]:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Auth transaction is required")
        if not user_ids:
            return {}
        rows = session.execute(select(
            UserRow.user_id, UserRow.username_display,
        ).where(UserRow.user_id.in_(user_ids))).all()
        return {row.user_id: row.username_display for row in rows}
