from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.survey.application.create_version import (
    CreateSurveyVersion, SurveyOptionDraft, SurveyQuestionDraft, SurveySourceDraft,
    SurveyVersionCreateError, SurveyVersionCreateService,
)


def question(answer="TEXT"):
    return SurveyQuestionDraft(
        uuid.uuid4(), "Process", "How does it work?", "Discover current process",
        answer, {}, True, None, "A verified process description", False,
        (SurveyOptionDraft("YES", "Yes"), SurveyOptionDraft("NO", "No"))
        if answer == "SINGLE_CHOICE" else (),
        (SurveySourceDraft("MANUAL", manual_source_note="Facilitator prompt"),),
    )


class SurveyVersionCreateValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CreateSurveyVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 0,
            (question(), question("SINGLE_CHOICE")), (uuid.uuid4(),), str(uuid.uuid4()),
        )
        self.service = SurveyVersionCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), handover_sources=object(),
            capability_sources=object(), template_sources=object(), departments=object(),
            repository=object(), receipts=object(), audit=object(),
        )

    def invalid(self, command):
        with self.assertRaises(SurveyVersionCreateError) as caught:
            self.service.create(command)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_envelope_and_question_shape_fail_before_io(self):
        for change in ({"session_token": b"x"}, {"expected_lock_version": -1},
                       {"questions": ()}, {"target_department_ids": ()},
                       {"idempotency_key": "short"}):
            with self.subTest(change=change): self.invalid(replace(self.command, **change))
        self.invalid(replace(self.command, questions=(question("SINGLE_CHOICE"),
            replace(question("SINGLE_CHOICE"), options=()))))

    def test_source_shape_is_exclusive(self):
        bad = SurveySourceDraft("MANUAL", capability_item_row_id=uuid.uuid4(),
                                manual_source_note="bad")
        self.invalid(replace(self.command, questions=(replace(question(), sources=(bad,)),)))

    def test_secrets_are_redacted(self):
        value = repr(self.command)
        self.assertNotIn("s" * 32, value)
        self.assertNotIn(self.command.idempotency_key, value)


if __name__ == "__main__": unittest.main()
