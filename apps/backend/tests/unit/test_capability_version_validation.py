from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.capability.application.validate_version import (
    CapabilityVersionValidationError, CapabilityVersionValidationService,
    ValidateCapabilityVersion,
)


class CapabilityVersionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = ValidateCapabilityVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), str(uuid.uuid4()),
        )
        self.service = CapabilityVersionValidationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            sources=object(), evidence=object(), repository=object(),
            audit_source=object(), receipts=object(), audit=object(),
        )

    def test_invalid_identity_and_tokens_fail_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"baseline_id": uuid.UUID(int=0)},
            {"baseline_version_id": uuid.UUID(int=0)}, {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                    CapabilityVersionValidationError) as caught:
                self.service.validate(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_and_key_are_redacted(self) -> None:
        text = repr(self.command)
        self.assertNotIn("s" * 32, text)
        self.assertNotIn("c" * 32, text)
        self.assertNotIn(self.command.idempotency_key, text)


if __name__ == "__main__":
    unittest.main()
