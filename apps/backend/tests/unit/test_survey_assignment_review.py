from __future__ import annotations

import unittest, uuid
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.survey.application.review_assignment import ReviewSurveyAssignment, SurveyAssignmentReviewError, SurveyAssignmentReviewService
from plm_assistant.modules.survey.application.submission_views import CurrentSubmissionAnswer, SubmissionQuestion, SurveyAssignmentReviewReceipt, SurveyAssignmentSubmissionSnapshot

NOW=datetime(2026,10,6,tzinfo=timezone.utc)
ACTOR,PROJECT,ROUND,VERSION,ASSIGNMENT,QROW,QID,DEPT=(uuid.uuid4() for _ in range(8))

class Tx:
    commits=0
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def commit(self): type(self).commits+=1
class Access:
    def authenticated_user(self,*a,**k): return ACTOR
class Guard:
    def require_valid(self,**k): return object()
class Auth:
    def require_in_transaction(self,tx,**k): return AuthorizedProjectAction(ACTOR,PROJECT,k["operation"],"PROJECT_MANAGER")
class Repo:
    snapshot=SurveyAssignmentSubmissionSnapshot(ASSIGNMENT,ROUND,VERSION,PROJECT,DEPT,None,2,
        (SubmissionQuestion(QROW,QID,0,"TEXT",{},True,None,False,()),),
        (CurrentSubmissionAnswer(uuid.uuid4(),uuid.uuid4(),QROW,"ok","SELF_SERVICE",None,()),))
    def lock_snapshot(self,*a,**k): return self.snapshot
    def review_transition(self,tx,**k): return SurveyAssignmentReviewReceipt(ASSIGNMENT,ROUND,PROJECT,k["target_state"],'"v3"',k["return_comment"])
    def replay_review(self,*a,**k): return SurveyAssignmentReviewReceipt(ASSIGNMENT,ROUND,PROJECT,k["target_state"],'"v3"',k["return_comment"])
class Receipts:
    replay=None; completed=[]
    def reserve(self,*a,**k): return self.replay
    def complete(self,*a,**k): self.completed.append(k["result"])
class Audit:
    events=[]
    def append(self,tx,event): self.events.append(event); return uuid.uuid4()
class Evidence:
    def prove(self,*a,**k): raise AssertionError()

class SurveyAssignmentReviewTests(unittest.TestCase):
    def setUp(self):
        Tx.commits=0; Receipts.replay=None; Receipts.completed=[]; Audit.events=[]
        self.service=SurveyAssignmentReviewService(unit_of_work=Tx,access=Access(),license_guard=Guard(),authorization=Auth(),repository=Repo(),receipts=Receipts(),audit=Audit(),evidence_owner=Evidence(),clock=lambda:NOW)
        self.base=lambda comment: ReviewSurveyAssignment(b"s"*32,b"c"*32,uuid.uuid4(),PROJECT,ROUND,ASSIGNMENT,2,comment,str(uuid.uuid4()))
    def test_validate_rechecks_and_commits(self):
        result=self.service.validate(self.base(None))
        self.assertEqual(("VALIDATED",'"v3"'),(result.submission_state,result.etag)); self.assertEqual(1,Tx.commits)
    def test_return_normalizes_comment(self):
        result=self.service.return_assignment(self.base("  请补充证据  "))
        self.assertEqual("请补充证据",result.return_comment); self.assertEqual("SURVEY_ASSIGNMENT_RETURNED",Audit.events[0].action)
    def test_invalid_comment_and_wrong_method_shape_fail(self):
        with self.assertRaisesRegex(SurveyAssignmentReviewError,"VALIDATION_FAILED"): self.service.return_assignment(self.base("\x00"))
        with self.assertRaisesRegex(SurveyAssignmentReviewError,"VALIDATION_FAILED"): self.service.validate(self.base("not allowed"))

if __name__=="__main__": unittest.main()
