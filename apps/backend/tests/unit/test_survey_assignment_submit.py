from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.survey.application.submit_assignment import (
    SubmitSurveyAssignment, SurveyAssignmentSubmitError,
    SurveyAssignmentSubmitService,
)
from plm_assistant.modules.survey.application.submission_views import (
    CurrentSubmissionAnswer, SubmissionQuestion,
    SurveyAssignmentSubmissionSnapshot, SurveyAssignmentSubmitReceipt,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
ACTOR, PROJECT, ROUND, VERSION, ASSIGNMENT, QROW, QUESTION, DEPARTMENT = (
    uuid.uuid4() for _ in range(8))


class Tx:
    commits = 0
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs): return ACTOR


class Guard:
    def require_valid(self, **kwargs): return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(
            ACTOR, PROJECT, kwargs["operation"], "CUSTOMER_MEMBER")


class Repository:
    snapshot = SurveyAssignmentSubmissionSnapshot(
        ASSIGNMENT, ROUND, VERSION, PROJECT, DEPARTMENT, ACTOR, 1,
        (SubmissionQuestion(
            QROW, QUESTION, 0, "TEXT", {"min_length": 1}, True,
            None, False, ()),),
        (CurrentSubmissionAnswer(
            uuid.uuid4(), uuid.uuid4(), QROW, "answer",
            "SELF_SERVICE", None, ()),),
    )
    def lock_snapshot(self, transaction, **kwargs): return self.snapshot
    def submit(self, transaction, **kwargs):
        return SurveyAssignmentSubmitReceipt(
            ASSIGNMENT, ROUND, PROJECT, "SUBMITTED", '"v2"')
    def replay(self, transaction, **kwargs): return self.submit(transaction)


class Receipts:
    replay = None
    completed = []
    def reserve(self, transaction, **kwargs): return self.replay
    def complete(self, transaction, **kwargs): self.completed.append(kwargs["result"])


class Audit:
    events = []
    def append(self, transaction, event): self.events.append(event); return uuid.uuid4()


class Evidence:
    def prove(self, *args, **kwargs): raise AssertionError("no evidence expected")


class SurveyAssignmentSubmitTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0; Receipts.replay = None
        Receipts.completed = []; Audit.events = []
        self.repo = Repository()
        self.service = SurveyAssignmentSubmitService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=self.repo,
            receipts=Receipts(), audit=Audit(), evidence_owner=Evidence(),
            clock=lambda: NOW)
        self.command = SubmitSurveyAssignment(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, ROUND,
            ASSIGNMENT, 1, str(uuid.uuid4()))

    def test_complete_assignment_is_audited_receipted_and_committed(self):
        result = self.service.submit(self.command)
        self.assertEqual(("SUBMITTED", '"v2"'),
                         (result.submission_state, result.etag))
        self.assertEqual("SURVEY_ASSIGNMENT_SUBMITTED", Audit.events[0].action)
        self.assertEqual(ASSIGNMENT, Receipts.completed[0].ref_id)
        self.assertEqual(1, Tx.commits)

    def test_missing_required_answer_is_rejected_without_commit(self):
        self.repo.snapshot = replace(self.repo.snapshot, answers=())
        with self.assertRaisesRegex(
                SurveyAssignmentSubmitError, "SURVEY_ASSIGNMENT_INCOMPLETE"):
            self.service.submit(self.command)
        self.assertEqual(0, Tx.commits)

    def test_exact_receipt_replays_without_rechecking_mutable_answers(self):
        Receipts.replay = IdempotencyResult(
            "V1_SURVEY_ASSIGNMENT_SUBMIT", ASSIGNMENT, 200)
        result = self.service.submit(self.command)
        self.assertEqual('"v2"', result.etag)
        self.assertEqual(0, Tx.commits)

    def test_secret_fields_are_hidden_and_input_is_strict(self):
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn(self.command.idempotency_key, repr(self.command))
        with self.assertRaisesRegex(SurveyAssignmentSubmitError, "VALIDATION_FAILED"):
            self.service.submit(replace(self.command, expected_lock_version=-1))


if __name__ == "__main__": unittest.main()
