"""PlanVersion PROJECT Review Subject terminal Owner.

The Review command owns Review/Round/Decision/Receipt. This Owner binds the
terminal Review fact to the immutable PlanVersion lifecycle and Approved
pointer in that same caller transaction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewSubjectRead,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition, ReviewSubjectTransitionError,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState

from .plan_review_readiness import (
    PlanReviewReadinessDenied, PlanVersionReviewReadinessProof,
    PlanVersionReviewTerminalQuery, snapshot_fingerprint,
)
from .plan_review_subject import PlanReviewSubjectOwner
from .read_plan_version import PlanVersionSnapshotView


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


_CUSTOMER_CONFIRMERS = frozenset({"CUSTOMER_MANAGER", "CUSTOMER_MEMBER"})


@dataclass(frozen=True, slots=True)
class PlanReviewTerminalLock:
    snapshot: PlanVersionSnapshotView
    latest_version_id: uuid.UUID
    current_approved_version_ref: uuid.UUID | None

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not PlanVersionSnapshotView
                or not _id(self.latest_version_id)
                or self.current_approved_version_ref is not None
                and not _id(self.current_approved_version_ref)):
            raise ReviewSubjectAccessDenied()


class PlanVersionReviewSubjectOwner(PlanReviewSubjectOwner):
    """Registry-capable internal owner; does not itself expose HTTP/UI."""

    def __init__(self, *, repository, reviewers, readiness, audit) -> None:
        if audit is None:
            raise ValueError("Plan Review terminal Audit dependency required")
        super().__init__(repository=repository, reviewers=reviewers,
                         readiness=readiness)
        self._terminal_audit = audit

    def authorize_read(self, tx, *, user_id, project_id, subject_type,
                       subject_id, subject_version_id):
        if (not all(_id(value) for value in (user_id, project_id, subject_id))
                or subject_type != self.SUBJECT_TYPE
                or subject_version_id is not None and not _id(subject_version_id)
                or subject_version_id is not None and subject_version_id != subject_id):
            return None
        try:
            self._qualify_current(tx, project_id, (user_id,), ALL_MEMBERS)
        except ReviewSubjectAccessDenied:
            return None
        if self._repo.version_exists(
                tx, project_id=project_id, plan_version_id=subject_id) is not True:
            return None
        return AuthorizedReviewSubjectRead(
            user_id, project_id, subject_type, subject_id, subject_version_id)

    def require_transition_access_in_transaction(self, tx,
                                                 transition: ReviewSubjectTransition) -> None:
        self._require_transition(transition)
        before = self._transition_lock(tx, transition)
        try:
            self._qualify_current(
                tx, transition.before.review.project_id,
                transition.after_progress.reviewer_ids,
                _CUSTOMER_CONFIRMERS,
            )
        except ReviewSubjectAccessDenied:
            raise
        if transition.after_progress.state is ReviewRoundState.APPROVED:
            context = transition.proof_context
            if type(context) is not ReviewSubjectProofContext:
                raise ReviewSubjectAccessDenied()
            try:
                proof = self._readiness.prove_terminal_in_transaction(
                    tx, query=PlanVersionReviewTerminalQuery(
                        context.session_token, context.trace_id,
                        before.snapshot.project_id, before.snapshot.plan_id,
                        before.snapshot.plan_version_id,
                        transition.before.review.review_id,
                        transition.before.progress.round_id,
                        transition.before.subject_fingerprint,
                    ),
                )
            except PlanReviewReadinessDenied:
                raise ReviewSubjectAccessDenied() from None
            if (type(proof) is not PlanVersionReviewReadinessProof
                    or proof.project_id != before.snapshot.project_id
                    or proof.plan_id != before.snapshot.plan_id
                    or proof.plan_version_id != before.snapshot.plan_version_id
                    or proof.version_no != before.snapshot.version_no
                    or proof.content_fingerprint
                       != transition.before.subject_fingerprint):
                raise ReviewSubjectAccessDenied()

    def assert_transition_lock_in_transaction(self, tx,
                                              transition: ReviewSubjectTransition) -> None:
        self._require_transition(transition)
        self._transition_lock(tx, transition)

    def consume_terminal_in_transaction(self, tx,
                                        transition: ReviewSubjectTransition) -> None:
        self._require_transition(transition)
        if not transition.terminal:
            raise ReviewSubjectTransitionError()
        before = self._transition_lock(tx, transition)
        review_state = transition.after_progress.state
        version_state = self._terminal_version_state(transition)
        event_type = review_state.value
        result_id = self._repo.consume_terminal(
            tx, before=before, transition=transition,
            version_state=version_state, event_type=event_type,
        )
        if not _id(result_id):
            raise ReviewSubjectAccessDenied()
        self._terminal_audit.append(tx, AuditEventDraft(
            trace_id=transition.trace_id, event_scope="PROJECT",
            target_project_id=before.snapshot.project_id,
            actor_type="USER", actor_id=transition.actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action="PLAN_VERSION_REVIEW_" + review_state.value,
            outcome="SUCCESS", target_owner_module="plan",
            target_object_type=self.SUBJECT_TYPE,
            target_object_id=before.snapshot.plan_id,
            target_version_id=before.snapshot.plan_version_id,
            before_state="IN_REVIEW", after_state=version_state,
        ))

    def assert_terminal_consumed_in_transaction(
            self, tx, transition: ReviewSubjectTransition) -> None:
        self._require_transition(transition)
        if not transition.terminal:
            raise ReviewSubjectTransitionError()
        self._transition_lock(tx, transition, allow_terminal=True)
        result_id = self._repo.assert_terminal_consumed(
            tx, transition=transition,
            version_state=self._terminal_version_state(transition),
            event_type=transition.after_progress.state.value,
        )
        if not _id(result_id):
            raise ReviewSubjectAccessDenied()

    def require_transition_replay_access_in_transaction(
            self, tx, *, actor_id: uuid.UUID, review, result) -> None:
        version_id = getattr(result, "subject_version_id", None)
        if (not _id(actor_id) or not self._valid_review(review)
                or not _id(version_id) or review.subject_id != version_id
                or getattr(result, "review_id", None) != review.review_id):
            raise ReviewSubjectAccessDenied()
        try:
            self._qualify_current(tx, review.project_id, (actor_id,),
                                  ALL_MEMBERS)
        except ReviewSubjectAccessDenied:
            raise
        locked = self._repo.lock_subject(
            tx, project_id=review.project_id, plan_version_id=version_id)
        if (locked is None
                or locked.snapshot.review_ref != review.review_id
                or locked.snapshot.review_round_ref
                != getattr(result, "round_id", None)):
            raise ReviewSubjectAccessDenied()

    def _transition_lock(self, tx, transition, *, allow_terminal: bool = False
                         ) -> PlanReviewTerminalLock:
        self._require_transition(transition)
        review = transition.before.review
        locked = self._repo.lock_terminal_subject(
            tx, project_id=review.project_id,
            plan_id=None,
            plan_version_id=transition.before.subject_version_id,
        )
        if (type(locked) is not PlanReviewTerminalLock
                or locked.snapshot.project_id != review.project_id
                or locked.snapshot.plan_version_id
                   != transition.before.subject_version_id
                or review.subject_id != locked.snapshot.plan_version_id
                or locked.latest_version_id != transition.before.subject_version_id
                or locked.snapshot.review_ref != review.review_id
                or locked.snapshot.review_round_ref
                   != transition.before.progress.round_id
                or locked.snapshot.version_state != (
                    self._terminal_version_state(transition)
                    if allow_terminal and transition.terminal else "IN_REVIEW")
                or snapshot_fingerprint(locked.snapshot)
                   != transition.before.subject_fingerprint):
            raise ReviewSubjectAccessDenied()
        return locked

    def _qualify_current(self, tx, project_id, reviewer_ids, allowed_roles):
        try:
            facts = self._reviewers.qualify_in_transaction(
                tx, project_id=project_id, reviewer_ids=reviewer_ids,
                allowed_roles=allowed_roles)
        except ReviewReviewerEligibilityError:
            raise ReviewSubjectAccessDenied() from None
        if (type(facts) is not tuple or len(facts) != len(reviewer_ids)
                or any(type(fact) is not ProjectReviewerFacts
                       or fact.user_id != user_id
                       or fact.project_id != project_id
                       or fact.project_role not in allowed_roles
                       for fact, user_id in zip(facts, reviewer_ids))):
            raise ReviewSubjectAccessDenied()

    @staticmethod
    def _terminal_version_state(transition: ReviewSubjectTransition) -> str:
        state = transition.after_progress.state
        if state is ReviewRoundState.APPROVED:
            return "APPROVED"
        if state in (ReviewRoundState.RETURNED, ReviewRoundState.WITHDRAWN):
            return "RETURNED"
        raise ReviewSubjectTransitionError()

    @classmethod
    def _require_transition(cls, transition: ReviewSubjectTransition) -> None:
        if type(transition) is not ReviewSubjectTransition:
            raise ReviewSubjectTransitionError()
        transition.__post_init__()
        review = transition.before.review
        if (not cls._valid_review(review)
                or review.subject_id != transition.before.subject_version_id
                or transition.before.progress.round_id == uuid.UUID(int=0)):
            raise ReviewSubjectAccessDenied()
