from datetime import datetime,timezone
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4
from types import SimpleNamespace
import unittest
from sqlalchemy.exc import OperationalError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.review.application.subject_start import PreparedReviewSubject,ReviewSubjectStartPort
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot
from plm_assistant.modules.review.application.persist_round import StartedReviewRoundRef
from plm_assistant.modules.review.application.start_round import ReviewStartService,ReviewStartError,StartReviewRound
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository


class Tx:
    def __init__(self): self.committed=False
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def commit(self): self.committed=True


class ReviewStartTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        self.actor,self.project,self.review,self.round=uuid4(),uuid4(),uuid4(),uuid4()
        self.root=ReviewIdentitySnapshot(self.review,"PROJECT",self.project,"HND-02",uuid4(),"SYNTHETIC_ALL_V1","DRAFT",None,0)
        self.cmd=StartReviewRound(b"s"*32,b"c"*32,self.project,self.review,uuid4(),(uuid4(),),"SYNTHETIC_ALL_V1",0,uuid4())
        self.access,self.projects,self.users,self.projectfacts,self.guard,self.repo,self.receipts,self.audit=(Mock() for _ in range(8))
        self.owner=Mock(spec=ReviewSubjectStartPort)
        self.access.authenticated_user.return_value=self.actor
        self.projects.require_in_transaction.return_value=AuthorizedProjectAction(self.actor,self.project,"REVIEW_START_ROUND","PROJECT_MANAGER")
        self.users.lock_enabled_users.side_effect=lambda tx,ids:ids
        from plm_assistant.modules.project.application.authorization import ProjectActorFacts
        self.projectfacts.actor_facts.return_value=ProjectActorFacts("ACTIVE","CUSTOMER_MEMBER")
        self.qualify=ProjectReviewerQualificationService(users=self.users,projects=self.projectfacts)
        self.repo.lock_start_context.return_value=(self.root,self.round)
        self.repo.is_retryable_deadlock.side_effect=SqlAlchemyReviewStartRepository.is_retryable_deadlock
        self.owner.prepare_start_in_transaction.side_effect=lambda tx,r:PreparedReviewSubject(r,b"s"*32,1,self.now,r.reviewer_ids,())
        self.owner.assert_active_lock_in_transaction.return_value=None
        self.owner.require_start_replay_access_in_transaction.return_value=None
        self.result=StartedReviewRoundRef(self.round,self.review,self.project,1,self.cmd.subject_version_id,self.actor,self.now)
        self.repo.insert_round.return_value=self.result
        self.repo.get_started_ref.return_value=(self.result,tuple(sorted(self.cmd.reviewer_ids)))
        self.receipts.reserve.return_value=None
        self.txs=[]

    def uow(self):
        tx=Tx(); self.txs.append(tx); return tx
    def service(self,**k):return ReviewStartService(**(dict(unit_of_work=self.uow,access=self.access,projects=self.projects,
        reviewers=self.qualify,license_guard=self.guard,repository=self.repo,receipts=self.receipts,audit=self.audit,subjects=self.owner,clock=lambda:self.now)|k))
    def call(self,**k):return self.service(**k).start_idempotent(self.cmd,idempotency_key="synthetic-review-start-key")
    def denied(self,code,**k):
        with self.assertRaises(ReviewStartError) as exc:self.call(**k)
        self.assertEqual(exc.exception.code,code)
        self.assertFalse(any(t.committed for t in self.txs))

    def test_same_transaction_start_complete_commit(self):
        self.assertEqual(self.call(),self.result)
        self.assertTrue(self.txs[0].committed)
        for method in (self.users.lock_enabled_users,self.projects.require_in_transaction,self.projectfacts.actor_facts,self.repo.insert_round,self.receipts.complete,self.audit.append):
            self.assertTrue(all(c.args[0] is self.txs[0] for c in method.call_args_list))

    def test_success_replay_ignores_later_reviewer_disable_and_root_version(self):
        self.receipts.reserve.return_value=IdempotencyResult("V1_REVIEW_ROUND",self.round,201)
        self.users.lock_enabled_users.side_effect=lambda tx,ids:()
        self.repo.lock_start_context.return_value=(replace(self.root,state="IN_REVIEW",active_round_id=self.round,lock_version=1),uuid4())
        self.assertEqual(self.call(),self.result)
        self.projectfacts.actor_facts.assert_not_called()
        self.repo.insert_round.assert_not_called()
        self.audit.append.assert_not_called()

    def test_non_pm_cannot_probe_missing_reviewer_eligibility(self):
        self.users.lock_enabled_users.side_effect=lambda tx,ids:()
        self.projects.require_in_transaction.side_effect=ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        self.denied("RESOURCE_NOT_FOUND")
        self.repo.lock_start_context.assert_not_called()

    def test_missing_owner_and_new_ineligible_reviewer_rejected(self):
        self.denied("RESOURCE_NOT_FOUND",subjects=None)
        self.users.lock_enabled_users.side_effect=lambda tx,ids:()
        self.denied("REVIEW_REVIEWER_INELIGIBLE")
        self.repo.insert_round.assert_not_called()

    def test_wrong_replay_projection_or_replay_access_denial(self):
        self.receipts.reserve.return_value=IdempotencyResult("V1_REVIEW_ROUND",self.round,201)
        self.repo.get_started_ref.return_value=(replace(self.result,subject_version_id=uuid4()),self.cmd.reviewer_ids)
        self.denied("REVIEW_UNAVAILABLE")
        self.repo.get_started_ref.return_value=(self.result,self.cmd.reviewer_ids)
        self.owner.require_start_replay_access_in_transaction.return_value=True
        self.denied("RESOURCE_NOT_FOUND")

    def test_deadlock_only_retries_whole_uow_and_other_errors_do_not(self):
        failure=OperationalError("synthetic",{},SimpleNamespace(sqlstate="40P01"))
        self.receipts.reserve.side_effect=[failure,None]
        self.assertEqual(self.call(),self.result)
        self.assertEqual([t.committed for t in self.txs],[False,True])

    def test_exhausted_deadlock_retry_is_bounded(self):
        self.receipts.reserve.side_effect=OperationalError("synthetic",{},SimpleNamespace(sqlstate="40P01"))
        self.denied("REVIEW_UNAVAILABLE")
        self.assertEqual(len(self.txs),3)

    def test_request_validation_and_session_failure_before_eligibility(self):
        with self.assertRaises(ReviewStartError):self.service().start_idempotent(replace(self.cmd,reviewer_ids=()),idempotency_key="synthetic-review-start-key")
        self.guard.require_valid.assert_not_called()
        self.access.authenticated_user.return_value=None
        self.denied("AUTH_ACCESS_DENIED")
        self.users.lock_enabled_users.assert_not_called()
        self.assertNotIn("ssss",repr(self.cmd))
