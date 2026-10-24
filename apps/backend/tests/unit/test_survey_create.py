from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.survey.application.create_survey import (
    CreateSurvey, SurveyCreateError, SurveyCreateService,
)


class SurveyCreateValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CreateSurvey(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            "Business discovery", str(uuid.uuid4()),
        )
        self.service = SurveyCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(),
            audit=object(),
        )

    def test_untrusted_input_fails_before_io(self):
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"name": " padded "}, {"name": ""}, {"name": "x" * 256},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                    SurveyCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_and_key_are_redacted(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
