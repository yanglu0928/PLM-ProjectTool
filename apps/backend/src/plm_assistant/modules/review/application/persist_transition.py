"""Trusted caller transaction only; no authentication, UOW, commit or receipt."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from plm_assistant.modules.audit.application.public import AuditEventDraft
from .persist_round import ReviewRoundPersistError
from .read_snapshot import FixedReviewRoundSnapshot
from .subject_transition import ReviewSubjectTransition
from ..domain.round_progress import (ReviewRoundState, ReviewDecisionKind, ReviewDecisionSnapshot,
                                    ReviewWithdrawalSnapshot, _uuid, _utc)


@dataclass(frozen=True, slots=True)
class AppliedReviewTransitionRef:
    project_id: UUID
    review_id: UUID
    round_id: UUID
    subject_version_id: UUID
    actor_id: UUID
    occurred_at: datetime
    action: str
    state: ReviewRoundState
    review_after_version: int
    round_after_version: int
    decision_id: UUID | None

    def __post_init__(self):
        if (not all(_uuid(v) for v in (self.project_id,self.review_id,self.round_id,self.subject_version_id,self.actor_id))
                or not _utc(self.occurred_at) or type(self.state) is not ReviewRoundState
                or self.state is ReviewRoundState.PENDING
                or any(type(v) is not int or not 0 < v < 2**63 for v in (self.review_after_version,self.round_after_version))
                or self.review_after_version <= self.round_after_version
                or self.action not in ("DECIDE","WITHDRAW")
                or (self.action == "DECIDE" and (not _uuid(self.decision_id) or self.state is ReviewRoundState.WITHDRAWN))
                or (self.action == "WITHDRAW" and (self.decision_id is not None or self.state is not ReviewRoundState.WITHDRAWN))):
            raise ReviewRoundPersistError()


class ReviewTransitionPersistenceService:
    """Caller already holds current Actor/Project/License/command authorization.

    Owner remains mandatory and checks actual version-specific permissions/lock.
    Caller MUST roll back the whole transaction on any error, including audit or
    deferred commit failure. No production Owner/default success implementation.
    """
    def __init__(self, *, repository, audit, subjects=None, clock=None):
        if repository is None or audit is None:
            raise ValueError("Review transition dependencies required")
        self._repository, self._audit, self._subjects = repository, audit, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _before(self, tx, actor_id, project_id, review_id, round_id, trace_id):
        if not all(_uuid(v) for v in (actor_id,project_id,review_id,round_id,trace_id)):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if self._subjects is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        fixed = self._repository.lock_transition_context(tx, project_id=project_id, review_id=review_id, round_id=round_id)
        if fixed is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        if (type(fixed) is not FixedReviewRoundSnapshot or fixed.review.scope != "PROJECT"
                or fixed.review.project_id != project_id or fixed.review.review_id != review_id
                or fixed.progress.round_id != round_id):
            raise ReviewRoundPersistError()
        fixed.__post_init__()
        return fixed

    def _now(self, fixed):
        now = self._clock()
        if (not _utc(now) or now < fixed.progress.started_at or now < fixed.lock_acquired_at
                or any(now < d.decided_at for d in fixed.progress.decisions)):
            raise ReviewRoundPersistError()
        return now

    def decide_in_transaction(self, tx, *, actor_id, project_id, review_id, round_id, trace_id, decision, comment=None):
        fixed = self._before(tx,actor_id,project_id,review_id,round_id,trace_id)
        if actor_id not in fixed.progress.reviewer_ids:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        if any(d.reviewer_id == actor_id for d in fixed.progress.decisions):
            raise ReviewRoundPersistError("REVIEW_DECISION_EXISTS")
        if fixed.progress.state is not ReviewRoundState.IN_REVIEW:
            raise ReviewRoundPersistError("REVIEW_ROUND_STATE_INVALID")
        if type(decision) is not ReviewDecisionKind:
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if decision is ReviewDecisionKind.RETURN and (type(comment) is not str or not comment.strip()):
            raise ReviewRoundPersistError("REVIEW_COMMENT_REQUIRED")
        now = self._now(fixed)
        entry = ReviewDecisionSnapshot(self._repository.new_decision_id(tx),round_id,actor_id,decision,now,comment)
        return self._apply(tx,ReviewSubjectTransition(actor_id,trace_id,fixed,fixed.progress.record_decision(entry),now))

    def withdraw_in_transaction(self, tx, *, actor_id, project_id, review_id, round_id, trace_id, expected_version, reason=None):
        if type(expected_version) is not int or not 0 <= expected_version < 2**63-1:
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        fixed = self._before(tx,actor_id,project_id,review_id,round_id,trace_id)
        if fixed.review.lock_version != expected_version:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        if fixed.progress.state is not ReviewRoundState.IN_REVIEW:
            raise ReviewRoundPersistError("REVIEW_ROUND_STATE_INVALID")
        now = self._now(fixed)
        withdrawal = ReviewWithdrawalSnapshot(actor_id,now,reason)
        return self._apply(tx,ReviewSubjectTransition(actor_id,trace_id,fixed,fixed.progress.withdraw(withdrawal),now))

    def _apply(self, tx, intent):
        if self._subjects.require_transition_access_in_transaction(tx,intent) is not None:
            raise ReviewRoundPersistError()
        if self._subjects.assert_transition_lock_in_transaction(tx,intent) is not None:
            raise ReviewRoundPersistError()
        result = self._repository.apply_transition(tx,intent=intent)
        new, old = intent.after_progress, intent.before
        action = "WITHDRAW" if new.withdrawal is not None else "DECIDE"
        expected = AppliedReviewTransitionRef(old.review.project_id,old.review.review_id,new.round_id,
            old.subject_version_id,intent.actor_id,intent.occurred_at,action,new.state,
            old.review.lock_version+1,old.round_lock_version+1,
            None if action == "WITHDRAW" else new.decisions[-1].decision_id)
        if type(result) is not AppliedReviewTransitionRef or result != expected:
            raise ReviewRoundPersistError()
        result.__post_init__()
        if self._subjects.assert_transition_lock_in_transaction(tx,intent) is not None:
            raise ReviewRoundPersistError()
        if intent.terminal:
            if self._subjects.consume_terminal_in_transaction(tx,intent) is not None:
                raise ReviewRoundPersistError()
            if self._subjects.assert_terminal_consumed_in_transaction(tx,intent) is not None:
                raise ReviewRoundPersistError()
        self._audit.append(tx,AuditEventDraft(trace_id=intent.trace_id,event_scope="PROJECT",
            target_project_id=old.review.project_id,actor_type="USER",actor_id=intent.actor_id,
            original_actor_id=None,actor_hint_digest=None,action="REVIEW_WITHDRAWN" if action == "WITHDRAW" else "REVIEW_DECISION_RECORDED",
            outcome="SUCCESS",target_owner_module="review",target_object_type="RVW-02",
            target_object_id=new.round_id,before_state=old.progress.state.value,after_state=new.state.value))
        return result
