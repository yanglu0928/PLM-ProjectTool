"""CAP-01 GLOBAL decision requires a currently enabled assigned reviewer and receipt."""

from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult,
)
from plm_assistant.modules.review.application.global_capability_decide import (
    DecideGlobalCapabilityReview, GlobalCapabilityReviewDecisionError,
    GlobalCapabilityReviewDecisionService,
)
from plm_assistant.modules.review.application.global_persistence import (
    AppliedGlobalReviewTransitionRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import ReviewSubjectAccessDenied
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewRoundProgress, ReviewRoundState,
)


class Transaction:
    def __init__(self): self.commit = Mock()
    def __enter__(self): return self
    def __exit__(self, *_): return False


class GlobalCapabilityReviewDecisionTests(TestCase):
    def setUp(self):
        self.actor, self.review_id, self.round_id = uuid4(), uuid4(), uuid4()
        self.baseline_id, self.version_id = uuid4(), uuid4()
        self.now = datetime.now(timezone.utc)
        self.command = DecideGlobalCapabilityReview(
            b"s" * 32, b"c" * 32, uuid4(), self.review_id, self.round_id,
            ReviewDecisionKind.APPROVE, None, "synthetic-global-review-decision-001",
        )
        self.identity = ReviewIdentitySnapshot(
            self.review_id, "GLOBAL", None, "CAP-01", self.baseline_id,
            "DEPLOYMENT_ALL_V1", "IN_REVIEW", self.round_id, 1,
        )
        self.fixed = FixedReviewRoundSnapshot(
            self.identity, 1, self.version_id, self.actor,
            ReviewRoundProgress(self.round_id, self.now, (self.actor,)),
            (uuid4(),), 0, uuid4(), b"x" * 32, 1, self.now, (), uuid4(), self.now, None,
        )
        self.result = AppliedGlobalReviewTransitionRef(
            self.review_id, self.round_id, self.version_id, self.actor,
            self.now, "DECIDE", ReviewRoundState.APPROVED, 2, 1,
            uuid4(), uuid4(),
        )
        self.tx = Transaction()
        self.access, self.guard, self.repository = Mock(), Mock(), Mock()
        self.receipts, self.reviews, self.subject = Mock(), Mock(), Mock()
        self.access.authenticated_user.return_value = self.actor
        self.repository.lock_global_transition_context.return_value = self.fixed
        self.reviews.decide_in_transaction.return_value = self.result
        self.receipts.reserve.return_value = None
        self.repository.get_global_transition_ref.return_value = self.result
        self.subject.require_transition_replay_access_in_transaction.return_value = None

    def service(self):
        return GlobalCapabilityReviewDecisionService(
            unit_of_work=lambda: self.tx, access=self.access,
            license_guard=self.guard, repository=self.repository,
            receipts=self.receipts, reviews=self.reviews,
            subject=self.subject, clock=lambda: self.now,
        )

    def denied(self, code, command=None):
        with self.assertRaises(GlobalCapabilityReviewDecisionError) as caught:
            self.service().decide(command or self.command)
        self.assertEqual(caught.exception.code, code)

    def test_decision_uses_global_scope_and_commits_review_capability_receipt_together(self):
        result = self.service().decide(self.command)
        self.assertIs(result, self.result)
        self.repository.lock_global_transition_context.assert_called_once_with(
            self.tx, review_id=self.review_id, round_id=self.round_id,
        )
        self.reviews.decide_in_transaction.assert_called_once_with(
            self.tx, actor_id=self.actor, review_id=self.review_id,
            round_id=self.round_id, trace_id=self.command.trace_id,
            decision=ReviewDecisionKind.APPROVE, comment=None,
        )
        self.assertEqual(self.receipts.complete.call_args.kwargs["result"],
                         IdempotencyResult(
                             "V1_GLOBAL_CAP_REVIEW_TRANSITION", self.result.event_id, 200,
                         ))
        self.assertIsNone(self.receipts.complete.call_args.kwargs["scope"].project_id)
        self.tx.commit.assert_called_once()

    def test_same_key_replay_checks_current_access_and_does_not_commit_again(self):
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_GLOBAL_CAP_REVIEW_TRANSITION", self.result.event_id, 200,
        )
        self.assertIs(self.service().decide(self.command), self.result)
        self.repository.get_global_transition_ref.assert_called_once_with(
            self.tx, review_id=self.review_id, round_id=self.round_id,
            event_id=self.result.event_id,
        )
        self.subject.require_transition_replay_access_in_transaction.assert_called_once()
        self.reviews.decide_in_transaction.assert_not_called()
        self.tx.commit.assert_not_called()

    def test_expired_session_and_unassigned_user_cannot_decide(self):
        self.access.authenticated_user.return_value = None
        self.denied("AUTH_ACCESS_DENIED")
        self.repository.lock_global_transition_context.assert_not_called()
        self.access.authenticated_user.return_value = uuid4()
        self.denied("RESOURCE_NOT_FOUND")
        self.receipts.reserve.assert_not_called()

    def test_project_or_other_global_subject_is_denied_before_receipt(self):
        self.repository.lock_global_transition_context.return_value = replace(
            self.fixed, review=replace(self.identity, subject_type="HND-01"),
        )
        self.denied("RESOURCE_NOT_FOUND")
        self.repository.lock_global_transition_context.return_value = replace(
            self.fixed, review=replace(self.identity, scope="PROJECT", project_id=uuid4()),
        )
        self.denied("RESOURCE_NOT_FOUND")
        self.receipts.reserve.assert_not_called()

    def test_missing_return_comment_and_invalid_key_do_not_write(self):
        self.denied("VALIDATION_FAILED", replace(
            self.command, decision=ReviewDecisionKind.RETURN, comment=" ",
        ))
        self.guard.require_valid.assert_not_called()
        self.denied("VALIDATION_FAILED", replace(
            self.command, idempotency_key="short",
        ))
        self.receipts.reserve.assert_not_called()

    def test_license_and_current_source_failure_roll_back(self):
        self.guard.require_valid.side_effect = RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        self.denied("LICENSE_OPERATION_DENIED")
        self.tx.commit.assert_not_called()
        self.guard.require_valid.side_effect = None
        self.reviews.decide_in_transaction.side_effect = ReviewSubjectAccessDenied()
        self.denied("RESOURCE_NOT_FOUND")
        self.receipts.complete.assert_not_called()
        self.tx.commit.assert_not_called()

    def test_key_drift_or_untrusted_replay_cannot_make_another_decision(self):
        self.receipts.reserve.side_effect = IdempotencyError("CONFLICT_IDEMPOTENCY")
        self.denied("CONFLICT_IDEMPOTENCY")
        self.reviews.decide_in_transaction.assert_not_called()
        self.receipts.reserve.side_effect = None
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_GLOBAL_CAP_REVIEW_TRANSITION", self.result.event_id, 200,
        )
        self.repository.get_global_transition_ref.return_value = replace(
            self.result, actor_id=uuid4(),
        )
        self.denied("GLOBAL_REVIEW_UNAVAILABLE")
        self.subject.require_transition_replay_access_in_transaction.assert_not_called()
