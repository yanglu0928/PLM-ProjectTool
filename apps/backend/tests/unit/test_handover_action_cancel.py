from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.cancel_action import (
    CancelHandoverAction, HandoverActionCancelError,
    HandoverActionCancelService,
)


class HandoverActionCancelValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CancelHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            2, "No longer required", "cancel-key-0001",
        )

    def test_rejects_untrusted_or_incomplete_cancel(self):
        invalid = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"action_item_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"expected_version": True}, {"reason": ""},
            {"reason": " padded "}, {"reason": "x" * 2001},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionCancelError) as caught:
                HandoverActionCancelService._validate_and_payload(
                    replace(self.command, **values),
                )
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_payload_and_repr_are_stable_and_secret_safe(self):
        payload = HandoverActionCancelService._validate_and_payload(self.command)
        self.assertEqual("No longer required", payload["reason"])
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn("cancel-key-0001", rendered)


if __name__ == "__main__":
    unittest.main()
