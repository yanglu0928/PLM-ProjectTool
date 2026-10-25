from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4
import unittest

from plm_assistant.modules.review.application.global_persistence import (
    AppliedGlobalReviewTransitionRef,
    GlobalReviewPersistenceService,
    SubmittedGlobalReviewRef,
)
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import PreparedReviewSubject
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
    ReviewRoundProgress,
    ReviewRoundState,
)


class GlobalReviewPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.subject, self.version = uuid4(), uuid4(), uuid4()
        self.review, self.round, self.trace = uuid4(), uuid4(), uuid4()
        self.reviewer = uuid4()
        self.identity = ReviewIdentitySnapshot(
            self.review, "GLOBAL", None, "CAP-01", self.subject,
            "DEPLOYMENT_ALL_V1", "DRAFT", None, 0,
        )
        self.repository, self.audit = Mock(), Mock()
        self.subjects = Mock(spec=[
            "prepare_start_in_transaction",
            "assert_active_lock_in_transaction",
            "finalize_start_in_transaction",
            "require_start_replay_access_in_transaction",
            "require_transition_access_in_transaction",
            "assert_transition_lock_in_transaction",
            "consume_terminal_in_transaction",
            "assert_terminal_consumed_in_transaction",
            "require_transition_replay_access_in_transaction",
        ])
        self.repository.insert_global_identity.return_value = (
            self.identity, self.round,
        )
        self.subjects.prepare_start_in_transaction.side_effect = (
            lambda tx, request: PreparedReviewSubject(
                request, b"s" * 32, 1, self.now,
                request.reviewer_ids, (),
            )
        )
        self.subjects.assert_active_lock_in_transaction.return_value = None
        self.subjects.finalize_start_in_transaction.return_value = None
        self.subjects.require_transition_access_in_transaction.return_value = None
        self.subjects.assert_transition_lock_in_transaction.return_value = None
        self.subjects.consume_terminal_in_transaction.return_value = None
        self.subjects.assert_terminal_consumed_in_transaction.return_value = None
        self.submitted = SubmittedGlobalReviewRef(
            self.review, self.round, "CAP-01", self.subject, self.version,
            "DEPLOYMENT_ALL_V1", (self.reviewer,), self.actor, self.now,
        )
        self.repository.insert_global_round.return_value = self.submitted
        self.service = GlobalReviewPersistenceService(
            repository=self.repository, audit=self.audit,
            subjects=self.subjects, clock=lambda: self.now,
        )
        self.tx = object()

    def submit(self):
        return self.service.submit_in_transaction(
            self.tx, actor_id=self.actor, subject_type="CAP-01",
            subject_id=self.subject, subject_version_id=self.version,
            reviewer_ids=(self.reviewer,), policy_code="DEPLOYMENT_ALL_V1",
            trace_id=self.trace,
        )

    def active(self, reviewers=None, decisions=()):
        reviewers = reviewers or (self.reviewer,)
        progress = ReviewRoundProgress(
            self.round, self.now, reviewers, decisions,
        )
        root = replace(
            self.identity, state="IN_REVIEW", active_round_id=self.round,
            lock_version=1 + len(decisions),
        )
        return FixedReviewRoundSnapshot(
            root, 1, self.version, self.actor, progress,
            tuple(uuid4() for _ in reviewers), len(decisions), uuid4(),
            b"s" * 32, 1, self.now, (), uuid4(), self.now, None,
        )

    def test_submit_binds_global_owner_and_two_audit_events(self):
        self.assertEqual(self.submit(), self.submitted)
        request = self.subjects.prepare_start_in_transaction.call_args.args[1]
        self.assertEqual(request.review.scope, "GLOBAL")
        self.assertIsNone(request.review.project_id)
        self.assertEqual(self.subjects.assert_active_lock_in_transaction.call_count, 2)
        self.subjects.finalize_start_in_transaction.assert_called_once()
        self.assertEqual(self.audit.append.call_count, 2)
        self.assertTrue(all(call.args[0] is self.tx
                            for call in self.audit.append.call_args_list))

    def test_submit_rejects_missing_owner_or_unbound_result(self):
        with self.assertRaises(ReviewRoundPersistError) as caught:
            GlobalReviewPersistenceService(
                repository=self.repository, audit=self.audit,
                subjects=None, clock=lambda: self.now,
            ).submit_in_transaction(
                self.tx, actor_id=self.actor, subject_type="CAP-01",
                subject_id=self.subject, subject_version_id=self.version,
                reviewer_ids=(self.reviewer,),
                policy_code="DEPLOYMENT_ALL_V1", trace_id=self.trace,
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.repository.insert_global_round.return_value = replace(
            self.submitted, subject_version_id=uuid4(),
        )
        with self.assertRaises(ReviewRoundPersistError):
            self.submit()

    def test_submit_observes_started_time_after_subject_verification(self):
        events = []
        started = self.now + timedelta(microseconds=1)
        self.repository.insert_global_identity.side_effect = lambda *args, **kwargs: (
            events.append("identity") or (self.identity, self.round)
        )
        self.subjects.prepare_start_in_transaction.side_effect = lambda tx, request: (
            events.append("prepare") or PreparedReviewSubject(
                request, b"s" * 32, 1, self.now, request.reviewer_ids, (),
            )
        )
        self.repository.insert_global_round.return_value = replace(
            self.submitted, submitted_at=started,
        )
        service = GlobalReviewPersistenceService(
            repository=self.repository, audit=self.audit, subjects=self.subjects,
            clock=lambda: events.append("clock") or started,
        )
        result = service.submit_in_transaction(
            self.tx, actor_id=self.actor, subject_type="CAP-01",
            subject_id=self.subject, subject_version_id=self.version,
            reviewer_ids=(self.reviewer,), policy_code="DEPLOYMENT_ALL_V1",
            trace_id=self.trace,
        )
        self.assertEqual(started, result.submitted_at)
        self.assertEqual(["identity", "prepare", "clock"], events)

    def test_terminal_approval_requires_owner_consumption(self):
        fixed = self.active()
        self.repository.lock_global_transition_context.return_value = fixed
        decision_id, event_id = uuid4(), uuid4()
        self.repository.new_decision_id.return_value = decision_id
        self.repository.apply_global_transition.side_effect = lambda tx, intent: (
            AppliedGlobalReviewTransitionRef(
                self.review, self.round, self.version, self.reviewer,
                self.now, "DECIDE", ReviewRoundState.APPROVED, 2, 1,
                decision_id, event_id,
            )
        )
        result = self.service.decide_in_transaction(
            self.tx, actor_id=self.reviewer, review_id=self.review,
            round_id=self.round, trace_id=self.trace,
            decision=ReviewDecisionKind.APPROVE,
        )
        self.assertEqual(result.state, ReviewRoundState.APPROVED)
        self.subjects.consume_terminal_in_transaction.assert_called_once()
        self.subjects.assert_terminal_consumed_in_transaction.assert_called_once()
        self.assertEqual(self.audit.append.call_count, 1)

    def test_nonterminal_decision_does_not_consume_owner(self):
        other = uuid4()
        fixed = self.active((self.reviewer, other))
        self.repository.lock_global_transition_context.return_value = fixed
        decision_id, event_id = uuid4(), uuid4()
        self.repository.new_decision_id.return_value = decision_id
        self.repository.apply_global_transition.side_effect = lambda tx, intent: (
            AppliedGlobalReviewTransitionRef(
                self.review, self.round, self.version, self.reviewer,
                self.now, "DECIDE", ReviewRoundState.IN_REVIEW, 2, 1,
                decision_id, event_id,
            )
        )
        result = self.service.decide_in_transaction(
            self.tx, actor_id=self.reviewer, review_id=self.review,
            round_id=self.round, trace_id=self.trace,
            decision=ReviewDecisionKind.APPROVE,
        )
        self.assertEqual(result.state, ReviewRoundState.IN_REVIEW)
        self.subjects.consume_terminal_in_transaction.assert_not_called()

    def test_withdrawal_uses_expected_review_version_and_consumes(self):
        fixed = self.active()
        self.repository.lock_global_transition_context.return_value = fixed
        event_id = uuid4()
        self.repository.apply_global_transition.side_effect = lambda tx, intent: (
            AppliedGlobalReviewTransitionRef(
                self.review, self.round, self.version, self.actor,
                self.now, "WITHDRAW", ReviewRoundState.WITHDRAWN, 2, 1,
                None, event_id,
            )
        )
        result = self.service.withdraw_in_transaction(
            self.tx, actor_id=self.actor, review_id=self.review,
            round_id=self.round, trace_id=self.trace,
            expected_version=1, reason="scope changed",
        )
        self.assertEqual(result.state, ReviewRoundState.WITHDRAWN)
        self.subjects.consume_terminal_in_transaction.assert_called_once()
        with self.assertRaises(ReviewRoundPersistError) as caught:
            self.service.withdraw_in_transaction(
                self.tx, actor_id=self.actor, review_id=self.review,
                round_id=self.round, trace_id=self.trace,
                expected_version=2,
            )
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")


if __name__ == "__main__":
    unittest.main()
