"""SQL proof of the current Approved RequirementVersion for PrototypeVersion."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)

from .orm import RequirementRow, RequirementVersionRow


class SqlAlchemyPrototypeApprovedRequirementVersionProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> PrototypeApprovedRequirementVersionProof | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
            project_id, requirement_id, requirement_version_id,
        )):
            return None
        session = self._session(transaction)
        row = session.execute(select(
            RequirementVersionRow.project_id,
            RequirementVersionRow.requirement_id,
            RequirementVersionRow.requirement_version_id,
            RequirementVersionRow.version_no,
            RequirementVersionRow.content_fingerprint,
            RequirementVersionRow.review_ref,
            RequirementVersionRow.review_round_ref,
        ).join(
            RequirementRow,
            (RequirementRow.requirement_id == RequirementVersionRow.requirement_id)
            & (RequirementRow.project_id == RequirementVersionRow.project_id),
        ).where(
            RequirementRow.project_id == project_id,
            RequirementRow.requirement_id == requirement_id,
            RequirementRow.requirement_state == "ACTIVE",
            RequirementRow.current_approved_version_ref == requirement_version_id,
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.requirement_version_id == requirement_version_id,
            RequirementVersionRow.version_state == "APPROVED",
            RequirementVersionRow.review_ref.is_not(None),
            RequirementVersionRow.review_round_ref.is_not(None),
        ).with_for_update(
            read=True, of=(RequirementRow, RequirementVersionRow),
        )).one_or_none()
        if row is None:
            return None
        return PrototypeApprovedRequirementVersionProof(
            row.project_id, row.requirement_id, row.requirement_version_id,
            row.version_no, bytes(row.content_fingerprint).hex(),
            row.review_ref, row.review_round_ref,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Requirement transaction is required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Requirement transaction is required")
        return session
