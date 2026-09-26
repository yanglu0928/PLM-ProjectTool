from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from itertools import permutations, product
from uuid import UUID, uuid4
import unittest

from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind as K, ReviewDecisionSnapshot as D, ReviewProgressError,
    ReviewRoundProgress as R, ReviewRoundState as S, ReviewWithdrawalSnapshot as W,
)


class ReviewRoundProgressTests(unittest.TestCase):
    def setUp(self):
        self.ids = tuple(uuid4() for _ in range(3))
        self.time = datetime.now(timezone.utc)
        self.round = R(uuid4(), self.time, self.ids)

    def decision(self, reviewer, kind=K.APPROVE):
        return D(uuid4(), self.round.round_id, reviewer, kind, self.time,
                 "Please clarify the fixed version" if kind is K.RETURN else None)

    def test_all_combinations_and_orders_wait_for_complete_set(self):
        for choices in product((K.APPROVE, K.RETURN), repeat=3):
            decisions = tuple(self.decision(reviewer, choice) for reviewer, choice in zip(self.ids, choices))
            for order in permutations(decisions):
                progress = self.round
                for index, decision in enumerate(order):
                    old = progress
                    progress = progress.record_decision(decision)
                    self.assertEqual(len(old.decisions), index)
                    if index < 2:
                        self.assertIs(progress.state, S.IN_REVIEW)
                expected = S.RETURNED if K.RETURN in choices else S.APPROVED
                self.assertIs(progress.state, expected)
                self.assertEqual(progress.pending_reviewer_ids, ())

    def test_one_reviewer_finishes_immediately(self):
        for kind, expected in ((K.APPROVE, S.APPROVED), (K.RETURN, S.RETURNED)):
            progress = replace(self.round, reviewer_ids=self.ids[:1]).record_decision(self.decision(self.ids[0], kind))
            self.assertIs(progress.state, expected)

    def test_duplicate_reviewer_decision_identity_and_cross_round_rejected(self):
        decision = self.decision(self.ids[0])
        progress = self.round.record_decision(decision)
        for invalid in (decision, self.decision(self.ids[0], K.RETURN),
                        replace(self.decision(self.ids[1]), decision_id=decision.decision_id),
                        replace(self.decision(self.ids[1]), round_id=uuid4()), self.decision(uuid4())):
            with self.subTest(invalid=invalid), self.assertRaises(ReviewProgressError):
                progress.record_decision(invalid)

    def test_terminal_results_sealed(self):
        for kind in (K.APPROVE, K.RETURN):
            progress = replace(self.round, reviewer_ids=self.ids[:1]).record_decision(self.decision(self.ids[0], kind))
            with self.assertRaises(ReviewProgressError):
                progress.record_decision(self.decision(self.ids[1]))
            with self.assertRaises(ReviewProgressError):
                progress.withdraw(W(uuid4(), self.time))

    def test_withdraw_keeps_decisions_and_pending_assignments(self):
        progress = self.round.record_decision(self.decision(self.ids[0], K.RETURN))
        self.assertIs(progress.state, S.IN_REVIEW)
        withdrawn = progress.withdraw(W(uuid4(), self.time, "Owner withdraws this fixed version"))
        self.assertIs(withdrawn.state, S.WITHDRAWN)
        self.assertEqual(withdrawn.decisions, progress.decisions)
        self.assertEqual(withdrawn.pending_reviewer_ids, self.ids[1:])
        self.assertIs(progress.state, S.IN_REVIEW)
        with self.assertRaises(ReviewProgressError):
            withdrawn.record_decision(self.decision(self.ids[1]))
        with self.assertRaises(ReviewProgressError):
            withdrawn.withdraw(W(uuid4(), self.time))

    def test_reviewer_set_shape_uuid_and_nested_revalidation(self):
        for invalid in ((), list(self.ids), (self.ids[0], self.ids[0]), (UUID(int=0),), ("not-uuid",)):
            with self.subTest(invalid=invalid), self.assertRaises(ReviewProgressError):
                replace(self.round, reviewer_ids=invalid)
        with self.assertRaises(ReviewProgressError):
            replace(self.round, decisions=[])
        forged = self.decision(self.ids[0])
        object.__setattr__(forged, "reviewer_id", UUID(int=0))
        with self.assertRaises(ReviewProgressError):
            self.round.record_decision(forged)

    def test_return_comment_substantive_approve_optional_no_new_length_limit(self):
        for comment in (None, "", " \t\n", "\u3000", "\x00", 1):
            with self.subTest(comment=comment), self.assertRaises(ReviewProgressError):
                replace(self.decision(self.ids[0], K.RETURN), comment=comment)
        for comment in (None, "", "Confirmed", "x"*3000):
            replace(self.decision(self.ids[0]), comment=comment)
        with self.assertRaises(ReviewProgressError):
            replace(self.decision(self.ids[0]), kind="APPROVE")

    def test_utc_and_chronology(self):
        for time in (datetime.now(), self.time.astimezone(timezone(timedelta(hours=8))), "now"):
            with self.subTest(time=time), self.assertRaises(ReviewProgressError):
                replace(self.round, started_at=time)
            with self.assertRaises(ReviewProgressError):
                replace(self.decision(self.ids[0]), decided_at=time)
        with self.assertRaises(ReviewProgressError):
            self.round.record_decision(replace(self.decision(self.ids[0]), decided_at=self.time-timedelta(seconds=1)))
        decided = self.round.record_decision(replace(self.decision(self.ids[0]), decided_at=self.time+timedelta(seconds=1)))
        with self.assertRaises(ReviewProgressError):
            decided.withdraw(W(uuid4(), self.time))

    def test_immutable_and_safe_error(self):
        with self.assertRaises(FrozenInstanceError):
            self.round.reviewer_ids = ()
        with self.assertRaises(FrozenInstanceError):
            self.decision(self.ids[0]).comment = "Replace history"
        try:
            self.round.record_decision(self.decision(uuid4()))
        except ReviewProgressError as exc:
            self.assertEqual(str(exc), "invalid Review round progress")
