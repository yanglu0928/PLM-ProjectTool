from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.survey.application.submission_completeness import (
    SurveySubmissionIncomplete, evaluate_submission,
)
from plm_assistant.modules.survey.application.submission_views import (
    CurrentSubmissionAnswer, SubmissionEvidenceSnapshot, SubmissionQuestion,
    SurveyAssignmentSubmissionSnapshot,
)


class SurveySubmissionCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.project, self.round, self.version, self.assignment = (
            uuid.uuid4() for _ in range(4))
        self.first_id, self.second_id = uuid.uuid4(), uuid.uuid4()
        self.first_row, self.second_row = uuid.uuid4(), uuid.uuid4()
        self.first = SubmissionQuestion(
            self.first_row, self.first_id, 0, "SINGLE_CHOICE", {}, True,
            None, False, ("YES", "NO"))
        self.second = SubmissionQuestion(
            self.second_row, self.second_id, 1, "TEXT",
            {"min_length": 3, "max_length": 10}, True,
            {"question_ref": str(self.first_id), "operator": "EQUALS",
             "value": "YES"}, False, ())
        self.answer = CurrentSubmissionAnswer(
            uuid.uuid4(), uuid.uuid4(), self.first_row, "NO",
            "SELF_SERVICE", None, ())

    def snapshot(self, answers):
        return SurveyAssignmentSubmissionSnapshot(
            self.assignment, self.round, self.version, self.project,
            uuid.uuid4(), uuid.uuid4(), 1, (self.first, self.second), answers)

    def test_inactive_required_question_is_not_required(self):
        report = evaluate_submission(self.snapshot((self.answer,)), {})
        self.assertEqual((1, 1, 0), (
            report.active_question_count, report.answered_question_count,
            report.evidence_count))

    def test_active_required_and_validation_rule_fail_closed(self):
        yes = replace(self.answer, answer_value="YES")
        with self.assertRaises(SurveySubmissionIncomplete):
            evaluate_submission(self.snapshot((yes,)), {})
        short = CurrentSubmissionAnswer(
            uuid.uuid4(), uuid.uuid4(), self.second_row, "x",
            "SELF_SERVICE", None, ())
        with self.assertRaises(SurveySubmissionIncomplete):
            evaluate_submission(self.snapshot((yes, short)), {})

    def test_attachment_requires_fixed_value_evidence_and_extension(self):
        evidence_id = uuid.uuid4()
        evidence = SubmissionEvidenceSnapshot(
            evidence_id, uuid.uuid4(), uuid.uuid4(), 0, b"e" * 32)
        attachment = SubmissionQuestion(
            self.first_row, self.first_id, 0, "ATTACHMENT",
            {"min_files": 1, "max_files": 2,
             "allowed_extensions": [".pdf"]}, True, None, True, ())
        answer = CurrentSubmissionAnswer(
            uuid.uuid4(), uuid.uuid4(), self.first_row, [str(evidence_id)],
            "FACILITATED_RECORD", evidence_id, (evidence,))
        snapshot = replace(self.snapshot((answer,)), questions=(attachment,))
        self.assertEqual(1, evaluate_submission(
            snapshot, {evidence_id: "record.pdf"}).evidence_count)
        with self.assertRaises(SurveySubmissionIncomplete):
            evaluate_submission(snapshot, {evidence_id: "record.txt"})


if __name__ == "__main__": unittest.main()
