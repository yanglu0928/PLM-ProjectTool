"""Locked, scoped Evidence eligibility transition in a caller-owned transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.evidence.application.eligibility_record import LockedEvidenceEligibility
from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Evidence transaction is required")
    return session


class SqlAlchemyEvidenceEligibilityRepository:
    def lock(self, transaction: object, *, scope: str,
             project_id: uuid.UUID | None,
             evidence_id: uuid.UUID) -> LockedEvidenceEligibility | None:
        row = _session(transaction).execute(
            select(EvidenceRow).where(
                EvidenceRow.evidence_id == evidence_id,
                EvidenceRow.scope == scope,
                EvidenceRow.project_id == project_id,
            ).with_for_update(of=EvidenceRow),
        ).scalar_one_or_none()
        if row is None:
            return None
        return LockedEvidenceEligibility(
            row.evidence_id, row.scope, row.project_id,
            row.document_id, row.document_version_id,
            row.content_fingerprint, row.eligibility_state, row.lock_version,
        )

    def decide(self, transaction: object, *, locked: LockedEvidenceEligibility,
               state: str, reason: str, actor_id: uuid.UUID) -> int | None:
        if (type(locked) is not LockedEvidenceEligibility
                or locked.eligibility_state != "CANDIDATE"
                or state not in ("ELIGIBLE", "INELIGIBLE")
                or type(reason) is not str or not 1 <= len(reason) <= 1024
                or reason != reason.strip() or any(ord(char) < 32 for char in reason)
                or type(actor_id) is not uuid.UUID
                or actor_id.int == 0):
            raise ValueError("invalid Evidence eligibility transition")
        updated = _session(transaction).execute(
            update(EvidenceRow).where(
                EvidenceRow.evidence_id == locked.evidence_id,
                EvidenceRow.scope == locked.scope,
                EvidenceRow.project_id == locked.project_id,
                EvidenceRow.eligibility_state == "CANDIDATE",
                EvidenceRow.lock_version == locked.lock_version,
            ).values(
                eligibility_state=state, eligibility_reason=reason,
                updated_by=actor_id, updated_at=func.statement_timestamp(),
                lock_version=EvidenceRow.lock_version + 1,
            ).returning(EvidenceRow.lock_version),
        ).scalar_one_or_none()
        return updated
