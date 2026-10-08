"""Locked Prototype roots and immutable NOT_REQUIRED decision integrity.

This is a current-fact input to Workflow qualification, never a PASS by itself.
Review, Audit, Requirement and artifact proofs remain the Owner's responsibility.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass

from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)


@dataclass(frozen=True, slots=True)
class PrototypeDecisionLock:
    decision_id: uuid.UUID
    requirement_version_refs: tuple[uuid.UUID, ...]
    confirmed_by: uuid.UUID
    reason: str
    impact: str
    review_id: uuid.UUID | None
    review_round_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class PrototypeRootLock:
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    state: str
    current_approved_version_ref: uuid.UUID | None
    lock_version: int
    decision: PrototypeDecisionLock | None


def prove_not_required_decision(root: object, decision: object,
                                refs: object, result: object) -> PrototypeDecisionLock | None:
    """Reconcile all four locked rows, including the original hashed payload.

    ORM rows are deliberately accepted as objects so the same proof can be
    exercised with isolated row doubles without manufacturing database state.
    """
    if (root is None or decision is None or result is None
            or type(refs) is not tuple or not refs):
        return None
    try:
        if (root.prototype_state != "NOT_REQUIRED"
                or root.current_approved_version_ref is not None
                or decision.decision_type != "NOT_REQUIRED"
                or not (root.project_id == decision.project_id == result.project_id)
                or not (root.prototype_id == decision.prototype_id == result.prototype_id)
                or decision.scope_decision_id != result.scope_decision_id
                or root.lock_version != decision.after_version
                or root.lock_version != result.lock_version
                or decision.before_version + 1 != decision.after_version
                or not (root.updated_by == decision.confirmed_by == result.confirmed_by)
                or decision.reason != result.reason
                or decision.impact != result.impact
                or root.name != result.name
                or decision.review_id != result.review_id
                or decision.review_round_id != result.review_round_id
                or (decision.review_id is None) != (decision.review_round_id is None)
                or not isinstance(decision.decision_fingerprint, bytes)
                or not isinstance(result.decision_fingerprint, bytes)
                or not hmac.compare_digest(decision.decision_fingerprint,
                                           result.decision_fingerprint)):
            return None
        ordered = sorted(refs, key=lambda row: row.ordinal)
        values = tuple(row.requirement_version_id for row in ordered)
        if (any(row.ordinal != ordinal
                or row.scope_decision_id != decision.scope_decision_id
                or row.prototype_id != root.prototype_id
                or row.project_id != root.project_id
                or type(row.requirement_id) is not uuid.UUID
                or row.requirement_id.int == 0
                or type(row.requirement_version_id) is not uuid.UUID
                or row.requirement_version_id.int == 0
                for ordinal, row in enumerate(ordered, 1))
                or len(set(values)) != len(values)
                or tuple(result.requirement_version_refs) != values
                or values != tuple(sorted(values, key=str))):
            return None
        expected = canonical_payload_fingerprint({
            "project_id": str(root.project_id),
            "prototype_id": str(root.prototype_id),
            "expected_version": decision.before_version,
            "decision_type": "NOT_REQUIRED",
            "reason": decision.reason,
            "impact": decision.impact,
            "affected_requirement_version_refs": [str(value) for value in values],
        })
        if not hmac.compare_digest(expected, decision.decision_fingerprint):
            return None
        if (type(decision.confirmed_by) is not uuid.UUID
                or decision.confirmed_by.int == 0
                or type(decision.reason) is not str or not decision.reason.strip()
                or type(decision.impact) is not str or not decision.impact.strip()):
            return None
        return PrototypeDecisionLock(
            decision.scope_decision_id, values, decision.confirmed_by,
            decision.reason, decision.impact,
            decision.review_id, decision.review_round_id,
        )
    except (AttributeError, TypeError, ValueError):
        return None
