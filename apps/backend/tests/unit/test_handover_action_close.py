from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.close_action import (
    CloseHandoverAction, HandoverActionCloseError, HandoverActionCloseService,
)


class HandoverActionCloseValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CloseHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            3, uuid.uuid4(), "Resolution confirmed", "close-key-0001",
        )

    def test_rejects_untrusted_or_incomplete_close(self):
        invalid = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"action_item_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"expected_version": True},
            {"resolution_trace_ref": uuid.UUID(int=0)}, {"reason": ""},
            {"reason": " padded "}, {"reason": "x" * 2001},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionCloseError) as caught:
                HandoverActionCloseService._validate_and_payload(
                    replace(self.command, **values),
                )
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_payload_and_repr_are_stable_and_secret_safe(self):
        payload = HandoverActionCloseService._validate_and_payload(self.command)
        self.assertEqual(str(self.command.resolution_trace_ref),
                         payload["resolution_trace_ref"])
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn("close-key-0001", rendered)


if __name__ == "__main__":
    unittest.main()
