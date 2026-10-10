from dataclasses import replace
from datetime import datetime,timezone
from unittest.mock import Mock
from uuid import uuid4
import unittest
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot,FixedReviewRoundSnapshot
from plm_assistant.modules.review.application.persist_transition import AppliedReviewTransitionRef
from plm_assistant.modules.review.application.transition_command import (
    ReviewTransitionCommandService,ReviewTransitionCommandError,DecideReviewRound,WithdrawReviewRound,
)
from plm_assistant.modules.review.application.subject_transition import ReviewSubjectTransitionPort
from plm_assistant.modules.review.domain.round_progress import ReviewRoundProgress,ReviewDecisionKind,ReviewRoundState


class Tx:
    def __init__(self): self.commits=0;self.exited=False
    def __enter__(self): return self
    def __exit__(self,*args): self.exited=True;return False
    def commit(self): self.commits+=1


class TransitionCommandTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.actor,self.project,self.review,self.round=uuid4(),uuid4(),uuid4(),uuid4()
        root=ReviewIdentitySnapshot(self.review,"PROJECT",self.project,"HND-02",uuid4(),"SYNTHETIC_ALL_V1","IN_REVIEW",self.round,1)
        progress=ReviewRoundProgress(self.round,now,(self.actor,uuid4()))
        self.fixed=FixedReviewRoundSnapshot(root,1,uuid4(),uuid4(),progress,(uuid4(),uuid4()),0,
            uuid4(),b"s"*32,1,now,(),uuid4(),now,None)
        self.c=DecideReviewRound(b"s"*32,b"c"*32,self.project,self.review,self.round,uuid4(),ReviewDecisionKind.APPROVE,"synthetic private comment")
        self.w=WithdrawReviewRound(b"s"*32,b"c"*32,self.project,self.review,self.round,uuid4(),1,"synthetic private reason")
        self.result=AppliedReviewTransitionRef(self.project,self.review,self.round,self.fixed.subject_version_id,self.actor,now,
            "DECIDE",ReviewRoundState.IN_REVIEW,2,1,uuid4(),uuid4())
        self.access,self.projects,self.guard,self.repo,self.receipts,self.audit=Mock(),Mock(),Mock(),Mock(),Mock(),Mock()
        self.owner=Mock(spec=ReviewSubjectTransitionPort)
        self.owner.require_transition_replay_access_in_transaction.return_value=None
        self.access.authenticated_user.return_value=self.actor
        self.projects.require_in_transaction.side_effect=lambda tx,**k:AuthorizedProjectAction(self.actor,self.project,k["operation"],"PROJECT_MANAGER")
        self.repo.lock_transition_context.return_value=self.fixed
        self.repo.is_retryable_deadlock.return_value=False
        self.repo.get_transition_ref.return_value=self.result
        self.receipts.reserve.return_value=None
        self.txs=[]
        def uow():
            tx=Tx();self.txs.append(tx);return tx
        self.deps=dict(unit_of_work=uow,access=self.access,projects=self.projects,license_guard=self.guard,
            repository=self.repo,receipts=self.receipts,audit=self.audit,subjects=self.owner,clock=lambda:now)
        self.service=ReviewTransitionCommandService(**self.deps)
        self.persist=Mock()
        self.persist.decide_in_transaction.return_value=self.result
        self.persist.withdraw_in_transaction.return_value=replace(self.result,action="WITHDRAW",state=ReviewRoundState.WITHDRAWN,decision_id=None)
        self.service._persist=self.persist

    def decide(self,c=None):return self.service.decide_idempotent(c or self.c,idempotency_key="synthetic-decision-key")
    def test_new_decision_same_tx_event_receipt_and_commit(self):
        self.assertEqual(self.decide(),self.result)
        self.assertEqual(self.txs[0].commits,1)
        for method in (self.access.authenticated_user,self.projects.require_in_transaction,self.repo.lock_transition_context,
                       self.receipts.reserve,self.receipts.complete,self.persist.decide_in_transaction):
            self.assertIs(method.call_args.args[0],self.txs[0])
        self.assertEqual(self.receipts.complete.call_args.kwargs["result"],IdempotencyResult("V1_REVIEW_TRANSITION",self.result.event_id,200))

    def test_new_withdraw_keeps_root_version_reason_and_separate_operation(self):
        result=self.service.withdraw_idempotent(self.w,idempotency_key="synthetic-withdraw-key")
        self.assertEqual(result.action,"WITHDRAW")
        args=self.persist.withdraw_in_transaction.call_args.kwargs
        self.assertEqual(args["expected_version"],1)
        self.assertEqual(args["reason"],self.w.reason)
        self.assertEqual(self.receipts.reserve.call_args.kwargs["scope"].operation,"V1_REVIEW_WITHDRAW")

    def test_replay_original_ref_current_access_no_new_write_or_commit(self):
        self.receipts.reserve.return_value=IdempotencyResult("V1_REVIEW_TRANSITION",self.result.event_id,200)
        self.assertEqual(self.decide(),self.result)
        self.owner.require_transition_replay_access_in_transaction.assert_called_once()
        self.persist.decide_in_transaction.assert_not_called()
        self.receipts.complete.assert_not_called()
        self.assertEqual(self.txs[0].commits,0)
        self.owner.require_transition_replay_access_in_transaction.return_value=True
        with self.assertRaisesRegex(ReviewTransitionCommandError,"RESOURCE_NOT_FOUND"):self.decide()

    def test_revoked_project_permission_and_unassigned_before_receipt(self):
        self.access.authenticated_user.return_value=None
        with self.assertRaisesRegex(ReviewTransitionCommandError,"AUTH_ACCESS_DENIED"):self.decide()
        self.access.authenticated_user.return_value=self.actor
        self.projects.require_in_transaction.side_effect=ProjectAuthorizationError("PROJECT_ARCHIVED")
        with self.assertRaisesRegex(ReviewTransitionCommandError,"PROJECT_ARCHIVED"):self.decide()
        self.projects.require_in_transaction.side_effect=lambda tx,**k:AuthorizedProjectAction(self.actor,self.project,k["operation"],"CUSTOMER_MEMBER")
        with self.assertRaisesRegex(ReviewTransitionCommandError,"RESOURCE_NOT_FOUND"):
            self.service.withdraw_idempotent(self.w,idempotency_key="synthetic-withdraw-key")
        self.repo.lock_transition_context.return_value=replace(self.fixed,
            progress=replace(self.fixed.progress,reviewer_ids=(uuid4(),uuid4())))
        with self.assertRaisesRegex(ReviewTransitionCommandError,"RESOURCE_NOT_FOUND"):self.decide()
        self.receipts.reserve.assert_not_called()

    def test_missing_owner_and_wrong_replay_binding_fail_closed(self):
        missing=ReviewTransitionCommandService(**(self.deps|dict(subjects=None)))
        with self.assertRaisesRegex(ReviewTransitionCommandError,"RESOURCE_NOT_FOUND"):
            missing.decide_idempotent(self.c,idempotency_key="synthetic-decision-key")
        self.receipts.reserve.return_value=IdempotencyResult("V1_REVIEW_TRANSITION",self.result.event_id,200)
        self.repo.get_transition_ref.return_value=replace(self.result,actor_id=uuid4())
        with self.assertRaisesRegex(ReviewTransitionCommandError,"REVIEW_UNAVAILABLE"):self.decide()

    def test_safe_repr_and_invalid_body_session_kind_rejected(self):
        self.assertNotIn("synthetic private",repr(self.c))
        self.assertNotIn("synthetic private",repr(self.w))
        self.assertNotIn(repr(self.c.session_token),repr(self.c))
        for command in (replace(self.c,decision="APPROVE"),replace(self.c,comment="x\x00y"),replace(self.c,session_token=b"short")):
            with self.assertRaisesRegex(ReviewTransitionCommandError,"VALIDATION_FAILED"):self.decide(command)
        with self.assertRaisesRegex(ReviewTransitionCommandError,"REVIEW_COMMENT_REQUIRED"):
            self.decide(replace(self.c,decision=ReviewDecisionKind.RETURN,comment=" "))
        self.guard.require_valid.assert_not_called()

    def test_whole_uow_deadlock_retry_and_bound(self):
        self.repo.lock_transition_context.side_effect=[RuntimeError("synthetic deadlock"),self.fixed]
        self.repo.is_retryable_deadlock.side_effect=lambda exc:str(exc)=="synthetic deadlock"
        self.assertEqual(self.decide(),self.result)
        self.assertEqual(len(self.txs),2)
        self.assertTrue(self.txs[0].exited)
        self.assertEqual([tx.commits for tx in self.txs],[0,1])
        self.repo.lock_transition_context.side_effect=RuntimeError("synthetic deadlock")
        before=len(self.txs)
        with self.assertRaisesRegex(ReviewTransitionCommandError,"REVIEW_UNAVAILABLE"):self.decide()
        self.assertEqual(len(self.txs)-before,3)

    def test_receipt_failure_no_commit_no_unknown_retry(self):
        self.receipts.complete.side_effect=RuntimeError("synthetic receipt failure")
        with self.assertRaisesRegex(ReviewTransitionCommandError,"REVIEW_UNAVAILABLE"):self.decide()
        self.assertEqual(len(self.txs),1)
        self.assertEqual(self.txs[0].commits,0)
