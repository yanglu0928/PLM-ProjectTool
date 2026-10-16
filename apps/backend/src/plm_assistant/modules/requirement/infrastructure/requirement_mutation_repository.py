"""Requirement identity mutation persistence and evidence proof."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow
from plm_assistant.modules.requirement.application.mutate_requirement import (
    RequirementIdentityView, RequirementMutationError,
)
from .orm import (
    RequirementCommandResultRow, RequirementDecisionEvidenceRefRow,
    RequirementRow, RequirementStateDecisionRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Requirement transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Requirement transaction is required")
    return session


def _view(row: RequirementCommandResultRow) -> RequirementIdentityView:
    return RequirementIdentityView(
        row.requirement_id, row.project_id, row.requirement_code,
        row.requirement_state, row.decision_id, row.reason, row.impact,
        tuple(row.evidence_refs), f'"v{row.lock_version}"',
    )


class SqlAlchemyRequirementMutationRepository:
    def mutate(self, transaction: object, *, result_id: uuid.UUID,
               decision_id: uuid.UUID | None, operation: str, project_id: uuid.UUID,
               requirement_id: uuid.UUID, expected_version: int, actor_id: uuid.UUID,
               requirement_code: str | None, reason: str | None, impact: str | None,
               evidence_ids: tuple[uuid.UUID, ...]) -> RequirementIdentityView:
        session = _session(transaction)
        root = session.execute(select(RequirementRow).where(
            RequirementRow.requirement_id == requirement_id,
            RequirementRow.project_id == project_id,
        ).with_for_update(of=RequirementRow)).scalar_one_or_none()
        if root is None:
            raise RequirementMutationError("RESOURCE_NOT_FOUND")
        if root.lock_version != expected_version:
            raise RequirementMutationError("CONFLICT_VERSION")
        if root.requirement_state == "ARCHIVED":
            raise RequirementMutationError("REQUIREMENT_STATE_INVALID")

        new_code, new_state = root.requirement_code, root.requirement_state
        if operation == "PATCH":
            if root.requirement_state != "ACTIVE":
                raise RequirementMutationError("REQUIREMENT_STATE_INVALID")
            if requirement_code == root.requirement_code:
                raise RequirementMutationError("CONFLICT_NO_CHANGE")
            new_code = requirement_code
        elif operation in {"DEFER", "REJECT"}:
            if root.requirement_state != "ACTIVE" or decision_id is None:
                raise RequirementMutationError("REQUIREMENT_STATE_INVALID")
            eligible = set(session.execute(select(EvidenceRow.evidence_id).where(
                EvidenceRow.evidence_id.in_(evidence_ids), EvidenceRow.scope == "PROJECT",
                EvidenceRow.project_id == project_id,
                EvidenceRow.eligibility_state == "ELIGIBLE",
            ).with_for_update(of=EvidenceRow)).scalars())
            if eligible != set(evidence_ids):
                raise RequirementMutationError("REQUIREMENT_DECISION_INVALID")
            new_state = "DEFERRED" if operation == "DEFER" else "REJECTED"
        elif operation == "ARCHIVE":
            new_state = "ARCHIVED"
        else:
            raise RequirementMutationError("VALIDATION_FAILED")

        before_version = root.lock_version
        next_version = before_version + 1
        try:
            changed = session.execute(update(RequirementRow).where(
                RequirementRow.requirement_id == requirement_id,
                RequirementRow.project_id == project_id,
                RequirementRow.lock_version == before_version,
            ).values(
                requirement_code=new_code,
                requirement_code_normalized=new_code.upper(),
                requirement_state=new_state, updated_by=actor_id,
                updated_at=func.statement_timestamp(), lock_version=next_version,
            ))
        except IntegrityError as error:
            original = error.orig
            if (getattr(original, "sqlstate", None) == "23505"
                    and getattr(getattr(original, "diag", None), "constraint_name", None)
                    == "uq_req_requirements__project_code"):
                raise RequirementMutationError("CONFLICT_DUPLICATE") from None
            raise
        if changed.rowcount != 1:
            raise RequirementMutationError("CONFLICT_VERSION")

        if operation in {"DEFER", "REJECT"}:
            session.execute(insert(RequirementStateDecisionRow).values(
                decision_id=decision_id, requirement_id=requirement_id,
                project_id=project_id, decision_type=operation, reason=reason,
                impact=impact, decided_by=actor_id, before_version=before_version,
                after_version=next_version,
            ))
            session.execute(insert(RequirementDecisionEvidenceRefRow), [{
                "decision_id": decision_id, "requirement_id": requirement_id,
                "project_id": project_id, "evidence_id": evidence_id,
            } for evidence_id in evidence_ids])

        session.execute(insert(RequirementCommandResultRow).values(
            result_id=result_id, requirement_id=requirement_id, project_id=project_id,
            operation=operation, requirement_code=new_code,
            requirement_state=new_state, decision_id=decision_id,
            reason=reason, impact=impact, evidence_refs=list(evidence_ids),
            lock_version=next_version,
        ))
        return RequirementIdentityView(
            requirement_id, project_id, new_code, new_state, decision_id,
            reason, impact, evidence_ids, f'"v{next_version}"',
        )

    def result(self, transaction: object, *, result_id: uuid.UUID,
               project_id: uuid.UUID, requirement_id: uuid.UUID,
               operation: str) -> RequirementIdentityView | None:
        row = _session(transaction).execute(select(RequirementCommandResultRow).where(
            RequirementCommandResultRow.result_id == result_id,
            RequirementCommandResultRow.project_id == project_id,
            RequirementCommandResultRow.requirement_id == requirement_id,
            RequirementCommandResultRow.operation == operation,
        )).scalar_one_or_none()
        return None if row is None else _view(row)
