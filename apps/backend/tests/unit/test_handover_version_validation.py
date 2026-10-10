from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.validate_version import (
    HandoverVersionValidationError, HandoverVersionValidationService,
    ValidateHandoverVersion,
)


class HandoverVersionValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = ValidateHandoverVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()),
        )
        self.service = HandoverVersionValidationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), sources=object(), evidence=object(),
            capabilities=object(), ai_tasks=object(), repository=object(),
            audit_source=object(), receipts=object(), audit=object(),
        )

    def test_invalid_identity_and_tokens_fail_before_io(self):
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"handover_analysis_id": uuid.UUID(int=0)},
            {"handover_analysis_version_id": uuid.UUID(int=0)},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                    HandoverVersionValidationError) as caught:
                self.service.validate(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_reason_round_trip_is_bounded_and_ordered(self):
        issues = ("SOURCE_UNAVAILABLE", "CAPABILITY_UNAVAILABLE", "ACTION_ITEM_REQUIRED")
        reason = self.service._reason(issues)
        self.assertEqual(self.service._issues(reason), issues)
        self.assertLessEqual(len(reason), 64)

    def test_tokens_and_key_are_redacted(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
