"""Current Approved RequirementVersion acceptance IDs under project fence."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.requirement.application.prototype_workflow_proof import (
    RequirementAcceptanceRefsProof,
)

from .orm import (
    RequirementAcceptanceCriterionRow,
    RequirementRow,
    RequirementVersionRow,
)
from .prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof


class SqlAlchemyRequirementAcceptanceRefsProof:
    """Expose only stable IDs, not raw Requirement rows or text to Prototype."""

    def prove_current_acceptance_refs(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> RequirementAcceptanceRefsProof | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in (
                project_id, requirement_id, requirement_version_id)):
            return None
        session = SqlAlchemyPrototypeApprovedRequirementVersionProof._session(
            transaction)
        version = session.execute(select(
            RequirementVersionRow.declared_acceptance_count,
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
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if type(version) is not int or version <= 0:
            return None
        rows = tuple(session.execute(select(
            RequirementAcceptanceCriterionRow,
        ).where(
            RequirementAcceptanceCriterionRow.project_id == project_id,
            RequirementAcceptanceCriterionRow.requirement_id == requirement_id,
            RequirementAcceptanceCriterionRow.requirement_version_id
            == requirement_version_id,
        ).order_by(
            RequirementAcceptanceCriterionRow.ordinal,
        ).with_for_update(
            read=True, of=RequirementAcceptanceCriterionRow,
        ).execution_options(populate_existing=True)).scalars())
        if (len(rows) != version
                or tuple(row.ordinal for row in rows) != tuple(range(version))):
            return None
        try:
            return RequirementAcceptanceRefsProof(
                project_id, requirement_id, requirement_version_id,
                tuple(row.acceptance_criterion_id for row in rows),
            )
        except ValueError:
            return None
