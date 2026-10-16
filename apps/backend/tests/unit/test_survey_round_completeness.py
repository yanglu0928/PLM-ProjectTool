from __future__ import annotations

import unittest, uuid

from plm_assistant.modules.survey.application.round_completeness import SurveyRoundCompletenessContext, SurveyRoundCompletenessError, SurveyRoundCompletenessOwner, SurveyRoundCompletenessQuery
from plm_assistant.modules.survey.application.submission_views import CurrentSubmissionAnswer, SubmissionQuestion, SurveyAssignmentSubmissionSnapshot


PROJECT,ROUND,VERSION,DEPT,ASSIGNMENT,QROW,QID,ACTOR=(uuid.uuid4() for _ in range(8))
SNAPSHOT=SurveyAssignmentSubmissionSnapshot(
    ASSIGNMENT,ROUND,VERSION,PROJECT,DEPT,None,3,
    (SubmissionQuestion(QROW,QID,0,"TEXT",{},True,None,False,()),),
    (CurrentSubmissionAnswer(uuid.uuid4(),uuid.uuid4(),QROW,"answer","SELF_SERVICE",None,()),))

class Repo:
    context=SurveyRoundCompletenessContext(ROUND,VERSION,PROJECT,(DEPT,),((ASSIGNMENT,DEPT,3),))
    def lock_context(self,*a,**k): return self.context
class Submissions:
    def lock_snapshot(self,*a,**k): return SNAPSHOT
class Evidence:
    def prove(self,*a,**k): raise AssertionError()

class RoundCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.repo=Repo(); self.owner=SurveyRoundCompletenessOwner(repository=self.repo,submissions=Submissions(),evidence_owner=Evidence())
        self.query=SurveyRoundCompletenessQuery(b"s"*32,uuid.uuid4(),PROJECT,ROUND,ACTOR,"PROJECT_MANAGER")
    def test_nonempty_covered_validated_round_produces_stable_proof(self):
        first=self.owner.prove(object(),self.query); second=self.owner.prove(object(),self.query)
        self.assertEqual(first,second); self.assertEqual((1,1,1),(first.assignment_count,first.active_question_count,first.answered_question_count))
        self.assertEqual(32,len(first.report_fingerprint))
    def test_empty_or_uncovered_round_is_incomplete(self):
        for context in (
            SurveyRoundCompletenessContext(ROUND,VERSION,PROJECT,(DEPT,),()),
            SurveyRoundCompletenessContext(ROUND,VERSION,PROJECT,(DEPT,),((ASSIGNMENT,uuid.uuid4(),3),)),
        ):
            self.repo.context=context
            with self.assertRaises(SurveyRoundCompletenessError): self.owner.prove(object(),self.query)
    def test_invalid_actor_shape_fails_closed(self):
        with self.assertRaisesRegex(SurveyRoundCompletenessError,"RESOURCE_NOT_FOUND"):
            self.owner.prove(object(),SurveyRoundCompletenessQuery(b"x",uuid.uuid4(),PROJECT,ROUND,ACTOR,"CUSTOMER_MEMBER"))

if __name__=="__main__": unittest.main()
