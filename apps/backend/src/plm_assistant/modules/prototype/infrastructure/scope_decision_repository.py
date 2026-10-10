"""Atomic NOT_REQUIRED decision persistence and current-fact proof."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.mark_not_required import (
    PrototypeScopeDecisionError, PrototypeScopeDecisionView,
)
from plm_assistant.modules.requirement.infrastructure.orm import (
    RequirementRow, RequirementVersionRow,
)
from plm_assistant.modules.review.infrastructure.orm import (
    ReviewRoundRow, ReviewRow, ReviewSubjectSnapshotRow,
)
from .orm import (
    PrototypeRow, PrototypeScopeDecisionRequirementRefRow,
    PrototypeScopeDecisionResultRow, PrototypeScopeDecisionRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Prototype transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Prototype transaction is required")
    return session


def _view(row: PrototypeScopeDecisionResultRow) -> PrototypeScopeDecisionView:
    return PrototypeScopeDecisionView(
        row.prototype_id, row.project_id, row.name, "NOT_REQUIRED",
        row.scope_decision_id, row.reason, row.impact, row.confirmed_by,
        row.review_id, row.review_round_id,
        tuple(row.requirement_version_refs), row.decided_at,
        f'"v{row.lock_version}"',
    )


class SqlAlchemyPrototypeScopeDecisionRepository:
    def decide(
        self, transaction: object, *, result_id: uuid.UUID,
        scope_decision_id: uuid.UUID, project_id: uuid.UUID,
        prototype_id: uuid.UUID, expected_version: int, actor_id: uuid.UUID,
        reason: str, impact: str, decision_fingerprint: bytes,
        requirement_version_refs: tuple[uuid.UUID, ...],
        review_id: uuid.UUID | None, review_round_id: uuid.UUID | None,
    ) -> PrototypeScopeDecisionView:
        session = _session(transaction)
        root = session.execute(select(PrototypeRow).where(
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.project_id == project_id,
        ).with_for_update(of=PrototypeRow)).scalar_one_or_none()
        if root is None:
            raise PrototypeScopeDecisionError("RESOURCE_NOT_FOUND")
        if root.lock_version != expected_version:
            raise PrototypeScopeDecisionError("CONFLICT_VERSION")
        if root.prototype_state != "ACTIVE" or root.current_approved_version_ref is not None:
            raise PrototypeScopeDecisionError("PROTOTYPE_STATE_INVALID")

        approved_rows = session.execute(select(
            RequirementVersionRow.requirement_version_id,
            RequirementVersionRow.requirement_id,
            RequirementVersionRow.version_state,
            RequirementRow.current_approved_version_ref,
        ).join(
            RequirementRow,
            (RequirementRow.requirement_id == RequirementVersionRow.requirement_id)
            & (RequirementRow.project_id == RequirementVersionRow.project_id),
        ).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_version_id.in_(requirement_version_refs),
        ).order_by(
            RequirementVersionRow.requirement_version_id,
        ).with_for_update(of=(RequirementRow, RequirementVersionRow))).all()
        if (
            len(approved_rows) != len(requirement_version_refs)
            or any(
                row.version_state != "APPROVED"
                or row.current_approved_version_ref != row.requirement_version_id
                for row in approved_rows
            )
        ):
            raise PrototypeScopeDecisionError("PROTOTYPE_REQUIREMENT_NOT_APPROVED")
        requirement_by_version = {
            row.requirement_version_id: row.requirement_id for row in approved_rows
        }

        if review_id is not None:
            proof = session.execute(select(
                ReviewRow.review_id,
            ).join(
                ReviewRoundRow,
                (ReviewRoundRow.review_id == ReviewRow.review_id)
                & (ReviewRoundRow.scope == ReviewRow.scope)
                & (ReviewRoundRow.project_id == ReviewRow.project_id),
            ).join(
                ReviewSubjectSnapshotRow,
                (ReviewSubjectSnapshotRow.review_id == ReviewRow.review_id)
                & (ReviewSubjectSnapshotRow.review_round_id
                   == ReviewRoundRow.review_round_id),
            ).where(
                ReviewRow.review_id == review_id,
                ReviewRoundRow.review_round_id == review_round_id,
                ReviewRow.scope == "PROJECT", ReviewRow.project_id == project_id,
                ReviewRow.subject_type == "PRT_SCOPE_DECISION",
                ReviewRow.subject_id == prototype_id,
                ReviewRow.review_state == "APPROVED",
                ReviewRoundRow.round_state == "APPROVED",
                ReviewRoundRow.subject_version_id == prototype_id,
                ReviewSubjectSnapshotRow.subject_type == "PRT_SCOPE_DECISION",
                ReviewSubjectSnapshotRow.subject_id == prototype_id,
                ReviewSubjectSnapshotRow.subject_version_id == prototype_id,
                ReviewSubjectSnapshotRow.content_fingerprint == decision_fingerprint,
            ).with_for_update(of=(
                ReviewRow, ReviewRoundRow, ReviewSubjectSnapshotRow,
            ))).one_or_none()
            if proof is None:
                raise PrototypeScopeDecisionError("PROTOTYPE_NOT_REQUIRED_DECISION_MISSING")

        before_version = root.lock_version
        next_version = before_version + 1
        changed = session.execute(update(PrototypeRow).where(
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.project_id == project_id,
            PrototypeRow.lock_version == root.lock_version,
        ).values(
            prototype_state="NOT_REQUIRED", updated_by=actor_id,
            updated_at=func.statement_timestamp(), lock_version=next_version,
        ))
        if changed.rowcount != 1:
            raise PrototypeScopeDecisionError("CONFLICT_VERSION")
        decided_at = session.execute(insert(PrototypeScopeDecisionRow).values(
            scope_decision_id=scope_decision_id, prototype_id=prototype_id,
            project_id=project_id, decision_type="NOT_REQUIRED", reason=reason,
            impact=impact, decision_fingerprint=decision_fingerprint,
            confirmed_by=actor_id, review_id=review_id,
            review_round_id=review_round_id, before_version=before_version,
            after_version=next_version,
        ).returning(PrototypeScopeDecisionRow.decided_at)).scalar_one()
        session.execute(insert(PrototypeScopeDecisionRequirementRefRow), [{
            "scope_decision_id": scope_decision_id,
            "prototype_id": prototype_id,
            "project_id": project_id,
            "requirement_id": requirement_by_version[version_id],
            "requirement_version_id": version_id,
            "ordinal": ordinal,
        } for ordinal, version_id in enumerate(requirement_version_refs, 1)])
        session.execute(insert(PrototypeScopeDecisionResultRow).values(
            result_id=result_id, scope_decision_id=scope_decision_id,
            prototype_id=prototype_id, project_id=project_id, name=root.name,
            reason=reason, impact=impact,
            decision_fingerprint=decision_fingerprint, confirmed_by=actor_id,
            review_id=review_id, review_round_id=review_round_id,
            requirement_version_refs=list(requirement_version_refs),
            lock_version=next_version, decided_at=decided_at,
        ))
        return PrototypeScopeDecisionView(
            prototype_id, project_id, root.name, "NOT_REQUIRED", scope_decision_id,
            reason, impact, actor_id, review_id, review_round_id,
            requirement_version_refs, decided_at, f'"v{next_version}"',
        )

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
        project_id: uuid.UUID, prototype_id: uuid.UUID,
    ) -> PrototypeScopeDecisionView | None:
        row = _session(transaction).execute(select(
            PrototypeScopeDecisionResultRow,
        ).where(
            PrototypeScopeDecisionResultRow.result_id == result_id,
            PrototypeScopeDecisionResultRow.project_id == project_id,
            PrototypeScopeDecisionResultRow.prototype_id == prototype_id,
        )).scalar_one_or_none()
        return None if row is None else _view(row)
