from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.start_action import (
    HandoverActionStartError, HandoverActionStartService, StartHandoverAction,
)


class HandoverActionStartValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = StartHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            0, "Owner started work", "start-key-0001",
        )
        self.service = HandoverActionStartService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(),
            audit=object(),
        )

    def test_rejects_untrusted_command_fields(self):
        invalid = (
            {"session_token": b"short"},
            {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
            {"action_item_id": uuid.UUID(int=0)},
            {"expected_version": -1},
            {"expected_version": True},
            {"reason": ""},
            {"reason": " padded "},
            {"reason": "x" * 2001},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionStartError) as caught:
                self.service.start(replace(self.command, **values))
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_accepts_boundary_reason_lengths(self):
        self.service._validate(replace(self.command, reason="x"))
        self.service._validate(replace(self.command, reason="x" * 2000))

    def test_command_repr_redacts_credentials_and_idempotency_key(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn("start-key-0001", rendered)


if __name__ == "__main__":
    unittest.main()
