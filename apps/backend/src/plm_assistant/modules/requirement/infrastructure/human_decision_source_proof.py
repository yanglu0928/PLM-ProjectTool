"""Immutable DEFER/REJECT decision and Owner-result proof for Version sources."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select

from plm_assistant.modules.requirement.application.human_decision_source_proof import (
    RequirementHumanDecisionSourceProof,
)

from .orm import (
    RequirementCommandResultRow, RequirementDecisionEvidenceRefRow,
    RequirementStateDecisionRow,
)
from .requirement_mutation_repository import _session


class SqlAlchemyRequirementHumanDecisionSourceProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        decision_id: uuid.UUID,
    ) -> RequirementHumanDecisionSourceProof | None:
        if any(
            type(value) is not uuid.UUID or value.int == 0
            for value in (project_id, decision_id)
        ):
            return None
        session = _session(transaction)
        row = session.execute(select(
            RequirementStateDecisionRow.decision_id,
            RequirementStateDecisionRow.requirement_id,
            RequirementStateDecisionRow.project_id,
            RequirementStateDecisionRow.decision_type,
            RequirementStateDecisionRow.decided_by,
            RequirementStateDecisionRow.decided_at,
            RequirementStateDecisionRow.before_version,
            RequirementStateDecisionRow.after_version,
            RequirementCommandResultRow.evidence_refs,
        ).select_from(RequirementStateDecisionRow).join(
            RequirementCommandResultRow,
            (RequirementCommandResultRow.decision_id
             == RequirementStateDecisionRow.decision_id)
            & (RequirementCommandResultRow.requirement_id
               == RequirementStateDecisionRow.requirement_id)
            & (RequirementCommandResultRow.project_id
               == RequirementStateDecisionRow.project_id),
        ).where(
            RequirementStateDecisionRow.decision_id == decision_id,
            RequirementStateDecisionRow.project_id == project_id,
            RequirementCommandResultRow.operation
            == RequirementStateDecisionRow.decision_type,
            RequirementCommandResultRow.reason
            == RequirementStateDecisionRow.reason,
            RequirementCommandResultRow.impact
            == RequirementStateDecisionRow.impact,
            RequirementCommandResultRow.lock_version
            == RequirementStateDecisionRow.after_version,
            or_(
                and_(
                    RequirementStateDecisionRow.decision_type == "DEFER",
                    RequirementCommandResultRow.requirement_state == "DEFERRED",
                ),
                and_(
                    RequirementStateDecisionRow.decision_type == "REJECT",
                    RequirementCommandResultRow.requirement_state == "REJECTED",
                ),
            ),
        ).with_for_update(
            read=True,
            of=(RequirementStateDecisionRow, RequirementCommandResultRow),
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None:
            return None
        evidence = tuple(session.execute(select(
            RequirementDecisionEvidenceRefRow.evidence_id,
        ).where(
            RequirementDecisionEvidenceRefRow.decision_id == decision_id,
            RequirementDecisionEvidenceRefRow.requirement_id == row[1],
            RequirementDecisionEvidenceRefRow.project_id == project_id,
        ).order_by(
            RequirementDecisionEvidenceRefRow.evidence_id,
        ).with_for_update(
            read=True, of=RequirementDecisionEvidenceRefRow,
        ).execution_options(populate_existing=True)).scalars())
        expected = tuple(sorted(tuple(row[8]), key=str))
        if not evidence or evidence != expected:
            return None
        return RequirementHumanDecisionSourceProof(*row[:8], evidence)
