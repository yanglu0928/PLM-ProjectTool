"""Auth-owned eligible-manager check; Session/CSRF admin proof stays in Auth."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow


class SqlAlchemyProjectCreateAccess(SqlAlchemyLicenseImportAccess):
    def lock_eligible_manager(self, transaction: object, user_id: uuid.UUID) -> bool:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Auth transaction is required")
        row = session.execute(select(UserRow.user_id).where(
            UserRow.user_id == user_id,
            UserRow.state == "ENABLED",
        ).with_for_update(of=UserRow)).scalar_one_or_none()
        return row is not None
