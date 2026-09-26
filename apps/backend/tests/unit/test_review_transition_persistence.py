from dataclasses import replace
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from uuid import uuid4
import unittest
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot, FixedReviewRoundSnapshot
from plm_assistant.modules.review.application.persist_round import ReviewRoundPersistError
from plm_assistant.modules.review.application.persist_transition import ReviewTransitionPersistenceService, AppliedReviewTransitionRef
from plm_assistant.modules.review.application.subject_transition import ReviewSubjectTransitionPort
from plm_assistant.modules.review.domain.round_progress import ReviewRoundProgress, ReviewDecisionKind, ReviewDecisionSnapshot


class TransitionPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.users = (uuid4(),uuid4())
        progress = ReviewRoundProgress(uuid4(),self.now,self.users)
        root = ReviewIdentitySnapshot(uuid4(),"PROJECT",uuid4(),"HND-02",uuid4(),"SYNTHETIC_ALL_V1","IN_REVIEW",progress.round_id,1)
        self.fixed = FixedReviewRoundSnapshot(root,1,uuid4(),uuid4(),progress,(uuid4(),uuid4()),0,
            uuid4(),b"s"*32,1,self.now,(),uuid4(),self.now,None)
        self.tx,self.repo,self.audit,self.owner = Mock(),Mock(),Mock(),Mock(spec=ReviewSubjectTransitionPort)
        self.repo.lock_transition_context.return_value = self.fixed
        self.repo.new_decision_id.return_value = uuid4()
        self.owner.require_transition_access_in_transaction.return_value = None
        self.owner.assert_transition_lock_in_transaction.return_value = None
        self.owner.consume_terminal_in_transaction.return_value = None
        self.owner.assert_terminal_consumed_in_transaction.return_value = None
        def apply(tx,*,intent):
            f,n = intent.before,intent.after_progress
            return AppliedReviewTransitionRef(f.review.project_id,f.review.review_id,n.round_id,f.subject_version_id,
                intent.actor_id,intent.occurred_at,"WITHDRAW" if n.withdrawal else "DECIDE",n.state,
                f.review.lock_version+1,f.round_lock_version+1,None if n.withdrawal else n.decisions[-1].decision_id)
        self.repo.apply_transition.side_effect = apply
        self.args = dict(actor_id=self.users[0],project_id=root.project_id,review_id=root.review_id,
                         round_id=progress.round_id,trace_id=uuid4())

    def service(self,**kw):
        return ReviewTransitionPersistenceService(**(dict(repository=self.repo,audit=self.audit,subjects=self.owner,
                                                         clock=lambda:self.now)|kw))
    def decide(self,**kw):
        return self.service().decide_in_transaction(self.tx,**(self.args|dict(decision=ReviewDecisionKind.APPROVE)|kw))

    def test_partial_return_no_consume_same_tx_and_no_commit(self):
        result = self.decide(decision=ReviewDecisionKind.RETURN,comment="Please clarify")
        self.assertEqual(result.state,"IN_REVIEW")
        self.owner.consume_terminal_in_transaction.assert_not_called()
        self.owner.assert_terminal_consumed_in_transaction.assert_not_called()
        self.assertEqual(self.owner.assert_transition_lock_in_transaction.call_count,2)
        for method in (self.repo.apply_transition,self.audit.append,self.owner.require_transition_access_in_transaction,
                       self.owner.assert_transition_lock_in_transaction):
            self.assertTrue(all(call.args[0] is self.tx for call in method.call_args_list))
        self.tx.commit.assert_not_called()

    def test_final_approve_consumes_once_and_audits_no_comment_copy(self):
        decision = ReviewDecisionSnapshot(uuid4(),self.fixed.progress.round_id,self.users[1],ReviewDecisionKind.APPROVE,self.now)
        self.repo.lock_transition_context.return_value = replace(self.fixed,
            progress=self.fixed.progress.record_decision(decision),round_lock_version=1,
            review=replace(self.fixed.review,lock_version=2))
        result = self.decide(comment="private synthetic comment")
        self.assertEqual(result.state,"APPROVED")
        self.owner.consume_terminal_in_transaction.assert_called_once()
        self.owner.assert_terminal_consumed_in_transaction.assert_called_once()
        draft = self.audit.append.call_args.args[1]
        self.assertEqual(draft.action,"REVIEW_DECISION_RECORDED")
        self.assertNotIn("private synthetic comment",repr(draft))

    def test_withdraw_root_version_reason_and_pending_preserved(self):
        result = self.service().withdraw_in_transaction(self.tx,**self.args,expected_version=1,reason="Scope changed")
        self.assertEqual(result.state,"WITHDRAWN")
        intent = self.repo.apply_transition.call_args.kwargs["intent"]
        self.assertEqual(intent.after_progress.withdrawal.reason,"Scope changed")
        self.assertEqual(intent.after_progress.pending_reviewer_ids,self.users)
        self.owner.consume_terminal_in_transaction.assert_called_once()
        with self.assertRaisesRegex(ReviewRoundPersistError,"CONFLICT_VERSION"):
            self.service().withdraw_in_transaction(self.tx,**self.args,expected_version=0)

    def test_missing_owner_foreign_snapshot_and_unassigned_fail_closed(self):
        with self.assertRaisesRegex(ReviewRoundPersistError,"RESOURCE_NOT_FOUND"):
            self.service(subjects=None).decide_in_transaction(self.tx,**self.args,decision=ReviewDecisionKind.APPROVE)
        with self.assertRaisesRegex(ReviewRoundPersistError,"RESOURCE_NOT_FOUND"): self.decide(actor_id=uuid4())
        self.repo.lock_transition_context.return_value = replace(self.fixed,subject_version_id=uuid4(),
            review=replace(self.fixed.review,project_id=uuid4()))
        with self.assertRaises(ReviewRoundPersistError): self.decide()
        self.repo.apply_transition.assert_not_called()

    def test_duplicate_comment_kind_and_clock_rejection(self):
        with self.assertRaisesRegex(ReviewRoundPersistError,"REVIEW_COMMENT_REQUIRED"):
            self.decide(decision=ReviewDecisionKind.RETURN,comment=" ")
        with self.assertRaisesRegex(ReviewRoundPersistError,"VALIDATION_FAILED"): self.decide(decision="APPROVE")
        with self.assertRaises(ReviewRoundPersistError):
            self.service(clock=lambda:self.now-timedelta(seconds=1)).decide_in_transaction(self.tx,**self.args,decision=ReviewDecisionKind.APPROVE)
        d = ReviewDecisionSnapshot(uuid4(),self.fixed.progress.round_id,self.users[0],ReviewDecisionKind.APPROVE,self.now)
        self.repo.lock_transition_context.return_value = replace(self.fixed,progress=self.fixed.progress.record_decision(d),
            round_lock_version=1,review=replace(self.fixed.review,lock_version=2))
        with self.assertRaisesRegex(ReviewRoundPersistError,"REVIEW_DECISION_EXISTS"): self.decide()

    def test_boolean_permission_lock_and_consume_not_success(self):
        for method in ("require_transition_access_in_transaction","assert_transition_lock_in_transaction"):
            getattr(self.owner,method).return_value = True
            with self.assertRaises(ReviewRoundPersistError): self.decide()
            getattr(self.owner,method).return_value = None
        self.owner.consume_terminal_in_transaction.return_value = True
        with self.assertRaises(ReviewRoundPersistError):
            self.service().withdraw_in_transaction(self.tx,**self.args,expected_version=1)
        self.owner.consume_terminal_in_transaction.return_value = None
        self.owner.assert_terminal_consumed_in_transaction.return_value = True
        with self.assertRaises(ReviewRoundPersistError):
            self.service().withdraw_in_transaction(self.tx,**self.args,expected_version=1)
        self.audit.append.assert_not_called()

    def test_second_lock_or_audit_failure_propagates_to_caller_no_commit(self):
        self.owner.assert_transition_lock_in_transaction.side_effect = [None,RuntimeError("synthetic lock changed")]
        with self.assertRaises(RuntimeError): self.decide()
        self.audit.append.assert_not_called()
        self.owner.assert_transition_lock_in_transaction.side_effect = None
        self.audit.append.side_effect = RuntimeError("synthetic audit failed")
        with self.assertRaises(RuntimeError): self.decide()
        self.tx.commit.assert_not_called()

    def test_wrong_repository_result_rejected_before_consume(self):
        self.repo.apply_transition.side_effect = None
        self.repo.apply_transition.return_value = True
        with self.assertRaises(ReviewRoundPersistError): self.decide()
        self.owner.consume_terminal_in_transaction.assert_not_called()
        self.audit.append.assert_not_called()
