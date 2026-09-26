from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone, timedelta
import unittest
from uuid import uuid4

from plm_assistant.modules.review.application.read_snapshot import FixedReviewRoundSnapshot, ReviewIdentitySnapshot
from plm_assistant.modules.review.application.subject_transition import ReviewSubjectTransition, ReviewSubjectTransitionError
from plm_assistant.modules.review.domain.round_progress import (
    ReviewRoundProgress, ReviewDecisionSnapshot, ReviewDecisionKind, ReviewWithdrawalSnapshot,
)


class SubjectTransitionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.reviewers = (uuid4(), uuid4())
        self.progress = ReviewRoundProgress(uuid4(), self.now, self.reviewers)
        root = ReviewIdentitySnapshot(uuid4(), "PROJECT", uuid4(), "HND-02", uuid4(),
                                      "CUSTOMER_ALL_V1", "IN_REVIEW", self.progress.round_id, 1)
        self.before = FixedReviewRoundSnapshot(root, 1, uuid4(), uuid4(), self.progress,
            (uuid4(), uuid4()), 0, uuid4(), b"s"*32, 1, self.now, (), uuid4(), self.now, None)

    def decision(self, index=0, kind=ReviewDecisionKind.APPROVE):
        return ReviewDecisionSnapshot(uuid4(), self.progress.round_id, self.reviewers[index], kind,
                                      self.now, "Please correct" if kind is ReviewDecisionKind.RETURN else None)

    def intent(self, after, actor=None, before=None):
        return ReviewSubjectTransition(actor or self.reviewers[0], uuid4(), before or self.before, after, self.now)

    def test_first_return_keeps_lock_terminal_only_after_complete_set(self):
        first = self.progress.record_decision(self.decision(kind=ReviewDecisionKind.RETURN))
        self.assertFalse(self.intent(first).terminal)
        before = replace(self.before, progress=first, round_lock_version=1,
                         review=replace(self.before.review, lock_version=2))
        final = self.intent(first.record_decision(self.decision(1)), self.reviewers[1], before)
        self.assertTrue(final.terminal)
        self.assertEqual(final.after_progress.state, "RETURNED")

    def test_withdrawal_retains_pending_history_and_reason(self):
        withdrawal = ReviewWithdrawalSnapshot(uuid4(), self.now, "Scope changed")
        intent = self.intent(self.progress.withdraw(withdrawal), withdrawal.actor_id)
        self.assertTrue(intent.terminal)
        self.assertEqual(intent.after_progress.pending_reviewer_ids, self.reviewers)
        self.assertEqual(intent.after_progress.withdrawal.reason, "Scope changed")

    def test_cannot_proxy_decide_change_round_or_replace_old_decisions(self):
        first = self.progress.record_decision(self.decision())
        with self.assertRaises(ReviewSubjectTransitionError): self.intent(first, uuid4())
        for changed in (replace(first, round_id=uuid4(), decisions=()),
                        replace(first, reviewer_ids=tuple(reversed(self.reviewers))), self.progress):
            with self.assertRaises(ReviewSubjectTransitionError): self.intent(changed)
        before = replace(self.before, progress=first, round_lock_version=1,
                         review=replace(self.before.review, lock_version=2))
        altered = replace(first, decisions=(self.decision(),)).record_decision(self.decision(1))
        with self.assertRaises(ReviewSubjectTransitionError): self.intent(altered, self.reviewers[1], before)

    def test_exact_binding_and_immutability_not_fact_proof(self):
        intent = self.intent(self.progress.record_decision(self.decision()))
        intent.require_binding(intent)
        for changed in (replace(intent, trace_id=uuid4()),
                        replace(intent, before=replace(self.before, subject_version_id=uuid4())),
                        replace(intent, before=replace(self.before, subject_fingerprint=b"x"*32))):
            with self.assertRaises(ReviewSubjectTransitionError): intent.require_binding(changed)
        with self.assertRaises(FrozenInstanceError): intent.actor_id = uuid4()

    def test_time_counter_and_terminal_before_fail_closed(self):
        intent = self.intent(self.progress.record_decision(self.decision()))
        for changes in (dict(occurred_at=self.now+timedelta(seconds=1)), dict(actor_id=True),
                        dict(trace_id=None), dict(occurred_at=datetime.now()),
                        dict(before=replace(self.before, review=replace(self.before.review, lock_version=2**63-1)))):
            with self.assertRaises(ReviewSubjectTransitionError): replace(intent, **changes)
        withdrawn = self.progress.withdraw(ReviewWithdrawalSnapshot(uuid4(), self.now))
        closed = replace(self.before, progress=withdrawn, round_lock_version=1, lock_released_at=self.now,
                         review=replace(self.before.review, state="WITHDRAWN", active_round_id=None, lock_version=2))
        with self.assertRaises(ReviewSubjectTransitionError): self.intent(withdrawn, before=closed)
        self.assertEqual(str(ReviewSubjectTransitionError()), "Review Subject transition unavailable")
