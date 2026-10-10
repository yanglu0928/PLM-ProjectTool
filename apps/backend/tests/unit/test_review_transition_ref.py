from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import unittest
from sqlalchemy.orm import Session
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot, FixedReviewRoundSnapshot
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.persist_transition import AppliedReviewTransitionRef
from plm_assistant.modules.review.domain.round_progress import (
    ReviewRoundProgress, ReviewDecisionSnapshot, ReviewDecisionKind, ReviewWithdrawalSnapshot,
)
from plm_assistant.modules.review.infrastructure.transition_repository import SqlAlchemyReviewTransitionRepository


class TransitionRefTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.users,self.round,self.event = (uuid4(),uuid4()),uuid4(),uuid4()
        self.decisions = tuple(ReviewDecisionSnapshot(uuid4(),self.round,user,kind,self.now,
            "Synthetic correction" if kind is ReviewDecisionKind.RETURN else None)
            for user,kind in zip(self.users,(ReviewDecisionKind.RETURN,ReviewDecisionKind.APPROVE)))
        progress = ReviewRoundProgress(self.round,self.now,self.users,self.decisions)
        root = ReviewIdentitySnapshot(uuid4(),"PROJECT",uuid4(),"HND-02",uuid4(),"SYNTHETIC_ALL_V1","RETURNED",None,6)
        self.fixed = FixedReviewRoundSnapshot(root,2,uuid4(),uuid4(),progress,(uuid4(),uuid4()),2,
            uuid4(),b"s"*32,1,self.now,(),uuid4(),self.now,self.now)
        self.row = dict(after_lock_version=1,event_type="DECISION_RECORDED",actor_id=self.users[0],
            decision_id=self.decisions[0].decision_id,result_state="IN_REVIEW",occurred_at=self.now,withdrawal_reason=None)
        self.versions = [SimpleNamespace(decision_id=d.decision_id,round_after_version=i+1) for i,d in enumerate(self.decisions)]
        self.previous = [SimpleNamespace(round_no=1,round_state="APPROVED",lock_version=2)]
        self.repo = SqlAlchemyReviewTransitionRepository()
        self.repo.lock_transition_context = MagicMock(return_value=self.fixed)
        self.session = MagicMock(spec=Session)
        self.session.in_transaction.return_value = True
        self.tx = SimpleNamespace(session=self.session)
        self.args = dict(project_id=root.project_id,review_id=root.review_id,round_id=self.round,event_id=self.event)

    def get(self):
        event,versions,previous = MagicMock(),MagicMock(),MagicMock()
        event.mappings.return_value.one_or_none.return_value = self.row
        versions.all.return_value = self.versions
        previous.all.return_value = self.previous
        self.session.execute.side_effect = [event,versions,previous]
        return self.repo.get_transition_ref(self.tx,**self.args)

    def test_first_partial_response_not_current_terminal_state_or_root_counter(self):
        ref = self.get()
        self.assertEqual(ref.state,"IN_REVIEW")
        self.assertEqual(ref.review_after_version,5)
        self.assertEqual(ref.round_after_version,1)
        self.assertEqual(ref.event_id,self.event)
        self.assertEqual(ref.occurred_at,self.now)
        self.assertEqual(ref.actor_id,self.users[0])
        self.assertEqual(ref.subject_version_id,self.fixed.subject_version_id)
        self.assertNotEqual(ref.review_after_version,self.fixed.review.lock_version)

    def test_final_returned_ref_matches_complete_prefix(self):
        self.row.update(after_lock_version=2,actor_id=self.users[1],decision_id=self.decisions[1].decision_id,result_state="RETURNED")
        ref = self.get()
        self.assertEqual(ref.state,"RETURNED")
        self.assertEqual(ref.review_after_version,6)
        self.assertEqual(ref.round_after_version,2)

    def test_withdrawal_ref_preserves_actor_and_original_counter(self):
        actor = uuid4()
        progress = ReviewRoundProgress(self.round,self.now,self.users,self.decisions[:1],ReviewWithdrawalSnapshot(actor,self.now,"Synthetic scope"))
        self.fixed = replace(self.fixed,progress=progress,review=replace(self.fixed.review,state="WITHDRAWN"))
        self.repo.lock_transition_context.return_value = self.fixed
        self.versions = self.versions[:1]
        self.row.update(event_type="WITHDRAWN",after_lock_version=2,actor_id=actor,decision_id=None,
                        result_state="WITHDRAWN",withdrawal_reason="Synthetic scope")
        ref = self.get()
        self.assertEqual(ref.action,"WITHDRAW")
        self.assertEqual(ref.actor_id,actor)
        self.assertIsNone(ref.decision_id)

    def test_prefix_state_gap_previous_unsealed_or_actor_corruption_rejected(self):
        self.row["result_state"] = "RETURNED"
        with self.assertRaises(ReviewRoundPersistError): self.get()
        self.row["result_state"] = "IN_REVIEW"
        self.versions[1].round_after_version = 3
        with self.assertRaises(ReviewRoundPersistError): self.get()
        self.versions[1].round_after_version = 2
        self.previous[0].round_state = "IN_REVIEW"
        with self.assertRaises(ReviewRoundPersistError): self.get()
        self.previous[0].round_state = "APPROVED"
        self.row["actor_id"] = uuid4()
        with self.assertRaises(ReviewRoundPersistError): self.get()

    def test_missing_context_or_event_and_invalid_id_fail_closed(self):
        self.row = None
        self.assertIsNone(self.get())
        self.repo.lock_transition_context.return_value = None
        self.assertIsNone(self.get())
        with self.assertRaises(ReviewRoundPersistError): self.repo.get_transition_ref(self.tx,**(self.args|dict(event_id=True)))

    def test_result_ref_rejects_missing_event_or_inconsistent_shape(self):
        ref = self.get()
        for changes in (dict(event_id=None),dict(event_id=True),dict(review_after_version=1),dict(round_after_version=True),
                        dict(action="WITHDRAW"),dict(actor_id=None)):
            with self.assertRaises(ReviewRoundPersistError): replace(ref,**changes)
        self.assertIsInstance(ref,AppliedReviewTransitionRef)
