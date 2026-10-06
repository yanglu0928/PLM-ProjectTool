from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.survey.application.create_version import (
    SurveyOptionDraft, SurveyQuestionDraft, SurveySourceDraft,
)
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionSnapshot, SurveyVersionValidationError,
    SurveyVersionValidationService, ValidateSurveyVersion,
)


def question(*, question_id=None, answer_type="TEXT", options=(), validation=None,
             condition=None):
    return SurveyQuestionDraft(
        question_id or uuid.uuid4(), "Topic", "Question", "Objective", answer_type,
        {} if validation is None else validation, True, condition, "Expected", False,
        options, (SurveySourceDraft("MANUAL", manual_source_note="Facilitated"),),
    )


class SurveyVersionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = ValidateSurveyVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), str(uuid.uuid4()),
        )
        self.service = SurveyVersionValidationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), handover_sources=object(),
            capability_sources=object(), template_sources=object(),
            departments=object(), repository=object(), audit_source=object(),
            receipts=object(), audit=object(),
        )

    def test_invalid_identity_tokens_and_key_fail_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"survey_id": uuid.UUID(int=0)},
            {"survey_version_id": uuid.UUID(int=0)}, {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                    SurveyVersionValidationError) as caught:
                self.service.validate(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_and_key_are_redacted(self) -> None:
        text = repr(self.command)
        self.assertNotIn("s" * 32, text)
        self.assertNotIn("c" * 32, text)
        self.assertNotIn(self.command.idempotency_key, text)

    def test_valid_earlier_condition_has_no_question_issue(self) -> None:
        first = question(answer_type="SINGLE_CHOICE", options=(
            SurveyOptionDraft("YES", "Yes"), SurveyOptionDraft("NO", "No"),
        ))
        second = question(condition={
            "question_ref": str(first.question_id), "operator": "EQUALS",
            "value": "YES",
        })
        found: set[str] = set()
        SurveyVersionValidationService._question_issues(
            self._snapshot((first, second)), found,
        )
        self.assertEqual(found, set())

    def test_future_reference_and_cycle_are_reported_in_stable_order(self) -> None:
        first_id, second_id = uuid.uuid4(), uuid.uuid4()
        first = question(question_id=first_id, condition={
            "question_ref": str(second_id), "operator": "ANSWERED",
        })
        second = question(question_id=second_id, condition={
            "question_ref": str(first_id), "operator": "ANSWERED",
        })
        found: set[str] = set()
        SurveyVersionValidationService._question_issues(
            self._snapshot((first, second)), found,
        )
        self.assertEqual(found, {"CONDITION_REFERENCE_INVALID", "CONDITION_CYCLE"})

    def test_answer_rule_and_condition_value_mismatch_are_reported(self) -> None:
        first = question(answer_type="NUMBER", validation={
            "minimum": 10, "maximum": 1,
        })
        second = question(condition={
            "question_ref": str(first.question_id), "operator": "EQUALS",
            "value": "not-a-number",
        })
        found: set[str] = set()
        SurveyVersionValidationService._question_issues(
            self._snapshot((first, second)), found,
        )
        self.assertEqual(found, {"QUESTION_RULE_INVALID", "CONDITION_RULE_INVALID"})

    def _snapshot(self, questions):
        return SurveyVersionSnapshot(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1, "DRAFT", b"x" * 32,
            len(questions), sum(len(item.options) for item in questions),
            sum(len(item.sources) for item in questions), 1, tuple(questions),
            (uuid.uuid4(),), True,
        )


if __name__ == "__main__":
    unittest.main()
