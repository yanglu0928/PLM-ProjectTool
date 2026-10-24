from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.verify_action import (
    HandoverActionVerifyError, HandoverActionVerifyService,
    VerifyHandoverAction,
)


class HandoverActionVerifyValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = VerifyHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            2, (uuid.uuid4(),), "Response evidence verified",
            "verify-key-0001",
        )

    def test_rejects_untrusted_or_incomplete_verification(self):
        invalid = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"action_item_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"expected_version": True}, {"evidence_refs": ()},
            {"evidence_refs": (self.command.evidence_refs[0],) * 2},
            {"reason": ""}, {"reason": " padded "}, {"reason": "x" * 2001},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionVerifyError) as caught:
                HandoverActionVerifyService._validate_and_payload(
                    replace(self.command, **values),
                )
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_payload_preserves_evidence_order(self):
        evidence = (uuid.uuid4(), uuid.uuid4())
        payload = HandoverActionVerifyService._validate_and_payload(replace(
            self.command, evidence_refs=evidence,
        ))
        self.assertEqual([str(item) for item in evidence], payload["evidence_refs"])

    def test_command_repr_redacts_credentials_and_idempotency_key(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn("verify-key-0001", rendered)


if __name__ == "__main__":
    unittest.main()
