"""Project-owned non-removed membership check for candidate lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.infrastructure.orm import ProjectMemberRow


class SqlAlchemyMemberCandidateMembership:
    def is_unassigned(self, transaction: object, *, user_id: uuid.UUID) -> bool:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project transaction is required")
        return session.execute(select(ProjectMemberRow.project_member_id).where(
            ProjectMemberRow.user_id == user_id,
            ProjectMemberRow.state != "REMOVED",
        ).limit(1)).scalar_one_or_none() is None
