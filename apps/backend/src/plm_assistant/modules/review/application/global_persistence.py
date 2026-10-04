"""Trusted GLOBAL Review persistence; caller owns auth, idempotency and commit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from plm_assistant.modules.audit.application.public import AuditEventDraft

from ..domain.round_progress import (
    ReviewDecisionKind,
    ReviewDecisionSnapshot,
    ReviewRoundState,
    ReviewWithdrawalSnapshot,
    _utc,
    _uuid,
)
from .create_review import _code
from .persist_round import ReviewRoundPersistError
from .read_snapshot import FixedReviewRoundSnapshot, ReviewIdentitySnapshot
from .subject_start import PreparedReviewSubject, ReviewSubjectStartRequest
from .subject_transition import ReviewSubjectTransition


@dataclass(frozen=True, slots=True)
class SubmittedGlobalReviewRef:
    review_id: UUID
    round_id: UUID
    subject_type: str
    subject_id: UUID
    subject_version_id: UUID
    policy_code: str
    reviewer_ids: tuple[UUID, ...]
    submitted_by: UUID
    submitted_at: datetime
    review_after_version: int = 1
    round_no: int = 1

    def __post_init__(self) -> None:
        if (not all(_uuid(value) for value in (
                self.review_id, self.round_id, self.subject_id,
                self.subject_version_id, self.submitted_by))
                or not _code(self.subject_type, subject=True)
                or not _code(self.policy_code)
                or type(self.reviewer_ids) is not tuple
                or not self.reviewer_ids
                or any(not _uuid(value) for value in self.reviewer_ids)
                or len(set(self.reviewer_ids)) != len(self.reviewer_ids)
                or not _utc(self.submitted_at)
                or self.review_after_version != 1
                or self.round_no != 1):
            raise ReviewRoundPersistError()


@dataclass(frozen=True, slots=True)
class AppliedGlobalReviewTransitionRef:
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
    event_id: UUID

    def __post_init__(self) -> None:
        if (not all(_uuid(value) for value in (
                self.review_id, self.round_id, self.subject_version_id,
                self.actor_id, self.event_id))
                or not _utc(self.occurred_at)
                or type(self.state) is not ReviewRoundState
                or self.state is ReviewRoundState.PENDING
                or any(type(value) is not int or not 0 < value < 2**63
                       for value in (self.review_after_version,
                                     self.round_after_version))
                or self.review_after_version <= self.round_after_version
                or self.action not in ("DECIDE", "WITHDRAW")
                or self.action == "DECIDE" and (
                    not _uuid(self.decision_id)
                    or self.state is ReviewRoundState.WITHDRAWN)
                or self.action == "WITHDRAW" and (
                    self.decision_id is not None
                    or self.state is not ReviewRoundState.WITHDRAWN)):
            raise ReviewRoundPersistError()


class GlobalReviewPersistenceService:
    """Review-owned GLOBAL state machine inside the caller's transaction.

    The caller must authenticate and authorize current deployment/reviewer facts,
    reserve idempotency and commit or roll back the whole unit of work. Subject
    proof remains mandatory and is rechecked before and after Review writes.
    """

    def __init__(self, *, repository, audit, subjects=None, clock=None) -> None:
        if repository is None or audit is None:
            raise ValueError("GLOBAL Review persistence dependencies required")
        self._repository, self._audit, self._subjects = repository, audit, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit_in_transaction(
        self, tx, *, actor_id, subject_type, subject_id, subject_version_id,
        reviewer_ids, policy_code, trace_id,
    ) -> SubmittedGlobalReviewRef:
        if (not all(_uuid(value) for value in (
                actor_id, subject_id, subject_version_id, trace_id))
                or not _code(subject_type, subject=True)
                or not _code(policy_code)
                or type(reviewer_ids) is not tuple
                or not reviewer_ids
                or any(not _uuid(value) for value in reviewer_ids)
                or len(set(reviewer_ids)) != len(reviewer_ids)):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if self._subjects is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        now = self._now()
        identity, round_id = self._repository.insert_global_identity(
            tx, actor_id=actor_id, subject_type=subject_type,
            subject_id=subject_id, policy_code=policy_code,
        )
        if (type(identity) is not ReviewIdentitySnapshot
                or identity.scope != "GLOBAL"
                or identity.project_id is not None
                or identity.subject_type != subject_type
                or identity.subject_id != subject_id
                or identity.policy_code != policy_code
                or identity.state != "DRAFT"
                or identity.active_round_id is not None
                or identity.lock_version != 0
                or not _uuid(round_id)):
            raise ReviewRoundPersistError()
        request = ReviewSubjectStartRequest(
            actor_id, identity, round_id, subject_version_id, reviewer_ids,
        )
        prepared = self._subjects.prepare_start_in_transaction(tx, request)
        if type(prepared) is not PreparedReviewSubject:
            raise ReviewRoundPersistError()
        prepared.require_binding(request)
        if self._subjects.assert_active_lock_in_transaction(tx, request) is not None:
            raise ReviewRoundPersistError()
        if now < prepared.verified_at:
            raise ReviewRoundPersistError()
        result = self._repository.insert_global_round(
            tx, prepared=prepared, trace_id=trace_id, started_at=now,
        )
        expected = SubmittedGlobalReviewRef(
            identity.review_id, round_id, subject_type, subject_id,
            subject_version_id, policy_code, reviewer_ids, actor_id, now,
        )
        if result != expected or type(result) is not SubmittedGlobalReviewRef:
            raise ReviewRoundPersistError()
        result.__post_init__()
        finalizer = getattr(
            self._subjects, "finalize_start_in_transaction", None,
        )
        if finalizer is not None and finalizer(tx, request) is not None:
            raise ReviewRoundPersistError()
        if self._subjects.assert_active_lock_in_transaction(tx, request) is not None:
            raise ReviewRoundPersistError()
        self._audit.append(tx, AuditEventDraft(
            trace_id=trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER", actor_id=actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action="REVIEW_CREATED", outcome="SUCCESS",
            target_owner_module="review", target_object_type="RVW-01",
            target_object_id=identity.review_id, after_state="DRAFT",
        ))
        self._audit.append(tx, AuditEventDraft(
            trace_id=trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER", actor_id=actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action="REVIEW_STARTED", outcome="SUCCESS",
            target_owner_module="review", target_object_type="RVW-02",
            target_object_id=round_id, after_state="IN_REVIEW",
        ))
        return result

    def decide_in_transaction(
        self, tx, *, actor_id, review_id, round_id, trace_id,
        decision, comment=None,
    ) -> AppliedGlobalReviewTransitionRef:
        fixed = self._before(tx, actor_id, review_id, round_id, trace_id)
        if actor_id not in fixed.progress.reviewer_ids:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        if any(item.reviewer_id == actor_id for item in fixed.progress.decisions):
            raise ReviewRoundPersistError("REVIEW_DECISION_EXISTS")
        if fixed.progress.state is not ReviewRoundState.IN_REVIEW:
            raise ReviewRoundPersistError("REVIEW_ROUND_STATE_INVALID")
        if type(decision) is not ReviewDecisionKind:
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if decision is ReviewDecisionKind.RETURN and (
                type(comment) is not str or not comment.strip()):
            raise ReviewRoundPersistError("REVIEW_COMMENT_REQUIRED")
        now = self._now(fixed)
        entry = ReviewDecisionSnapshot(
            self._repository.new_decision_id(tx), round_id, actor_id,
            decision, now, comment,
        )
        return self._apply(tx, ReviewSubjectTransition(
            actor_id, trace_id, fixed,
            fixed.progress.record_decision(entry), now,
        ))

    def withdraw_in_transaction(
        self, tx, *, actor_id, review_id, round_id, trace_id,
        expected_version, reason=None,
    ) -> AppliedGlobalReviewTransitionRef:
        if type(expected_version) is not int or not 0 <= expected_version < 2**63 - 1:
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        fixed = self._before(tx, actor_id, review_id, round_id, trace_id)
        if fixed.review.lock_version != expected_version:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        if fixed.progress.state is not ReviewRoundState.IN_REVIEW:
            raise ReviewRoundPersistError("REVIEW_ROUND_STATE_INVALID")
        now = self._now(fixed)
        return self._apply(tx, ReviewSubjectTransition(
            actor_id, trace_id, fixed,
            fixed.progress.withdraw(ReviewWithdrawalSnapshot(
                actor_id, now, reason,
            )), now,
        ))

    def _before(self, tx, actor_id, review_id, round_id, trace_id):
        if not all(_uuid(value) for value in (
                actor_id, review_id, round_id, trace_id)):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if self._subjects is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        fixed = self._repository.lock_global_transition_context(
            tx, review_id=review_id, round_id=round_id,
        )
        if fixed is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        if (type(fixed) is not FixedReviewRoundSnapshot
                or fixed.review.scope != "GLOBAL"
                or fixed.review.project_id is not None
                or fixed.review.review_id != review_id
                or fixed.progress.round_id != round_id):
            raise ReviewRoundPersistError()
        fixed.__post_init__()
        return fixed

    def _now(self, fixed=None):
        now = self._clock()
        if not _utc(now):
            raise ReviewRoundPersistError()
        if fixed is not None and (
                now < fixed.progress.started_at
                or now < fixed.lock_acquired_at
                or any(now < item.decided_at
                       for item in fixed.progress.decisions)):
            raise ReviewRoundPersistError()
        return now

    def _apply(self, tx, intent):
        if self._subjects.require_transition_access_in_transaction(tx, intent) is not None:
            raise ReviewRoundPersistError()
        if self._subjects.assert_transition_lock_in_transaction(tx, intent) is not None:
            raise ReviewRoundPersistError()
        result = self._repository.apply_global_transition(tx, intent=intent)
        if type(result) is not AppliedGlobalReviewTransitionRef:
            raise ReviewRoundPersistError()
        new, old = intent.after_progress, intent.before
        action = "WITHDRAW" if new.withdrawal is not None else "DECIDE"
        expected = AppliedGlobalReviewTransitionRef(
            old.review.review_id, new.round_id, old.subject_version_id,
            intent.actor_id, intent.occurred_at, action, new.state,
            old.review.lock_version + 1, old.round_lock_version + 1,
            None if action == "WITHDRAW" else new.decisions[-1].decision_id,
            result.event_id,
        )
        if result != expected:
            raise ReviewRoundPersistError()
        result.__post_init__()
        if self._subjects.assert_transition_lock_in_transaction(tx, intent) is not None:
            raise ReviewRoundPersistError()
        if intent.terminal:
            if self._subjects.consume_terminal_in_transaction(tx, intent) is not None:
                raise ReviewRoundPersistError()
            if self._subjects.assert_terminal_consumed_in_transaction(tx, intent) is not None:
                raise ReviewRoundPersistError()
        self._audit.append(tx, AuditEventDraft(
            trace_id=intent.trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER",
            actor_id=intent.actor_id, original_actor_id=None,
            actor_hint_digest=None,
            action="REVIEW_WITHDRAWN" if action == "WITHDRAW"
                   else "REVIEW_DECISION_RECORDED",
            outcome="SUCCESS", target_owner_module="review",
            target_object_type="RVW-02", target_object_id=new.round_id,
            before_state=old.progress.state.value,
            after_state=new.state.value,
        ))
        return result
