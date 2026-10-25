"""Auth-owned exact eligible-user lookup, with no deployment directory exposure."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.domain.username import normalize_username
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyProjectMemberCandidateAccess(SqlAlchemyProjectWriteAccess):
    @staticmethod
    def canonical_username(raw: str) -> str:
        return normalize_username(raw).normalized

    def enabled_user(self, transaction: object, *, normalized_username: str
                     ) -> tuple[uuid.UUID, str] | None:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Auth transaction is required")
        row = session.execute(select(UserRow.user_id, UserRow.username_display).where(
            UserRow.username_normalized == normalized_username,
            UserRow.state == "ENABLED",
            UserRow.credential_version > 0,
            UserRow.active_password_credential_id.is_not(None),
        )).one_or_none()
        return None if row is None else (row.user_id, row.username_display)
