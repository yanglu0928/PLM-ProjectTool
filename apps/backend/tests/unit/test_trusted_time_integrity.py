from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.license.application.trusted_time import TrustedTimeError, TrustedTimeRecord
from plm_assistant.modules.license.infrastructure.trusted_time_integrity import HmacTrustedTimeIntegrity


class Resolver:
    def __init__(self, key: bytes | None) -> None:
        self.key = key

    def resolve_key(self, key_ref: str) -> bytes | None:
        return self.key if key_ref == "synthetic-test-key" else None


class TrustedTimeIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.integrity = HmacTrustedTimeIntegrity(Resolver(b"k" * 32), key_ref="synthetic-test-key")
        self.record = TrustedTimeRecord(uuid.uuid4(), datetime(2026, 9, 24, tzinfo=timezone.utc),
                                        1, None, uuid.uuid4())

    def test_valid_signature_and_every_bound_field_tamper(self) -> None:
        metadata = self.integrity.sign(self.record)
        signed = TrustedTimeRecord(self.record.state_id, self.record.last_successful_time,
                                   1, metadata, self.record.last_event_ref)
        self.assertTrue(self.integrity.verify(signed))
        for changed in (
            TrustedTimeRecord(uuid.uuid4(), signed.last_successful_time, 1, metadata, signed.last_event_ref),
            TrustedTimeRecord(signed.state_id, signed.last_successful_time, 2, metadata, signed.last_event_ref),
            TrustedTimeRecord(signed.state_id, datetime(2026, 9, 23, tzinfo=timezone.utc), 1, metadata, signed.last_event_ref),
            TrustedTimeRecord(signed.state_id, signed.last_successful_time, 1, metadata, uuid.uuid4()),
        ):
            self.assertFalse(self.integrity.verify(changed))

    def test_missing_key_and_malformed_metadata_fail_closed(self) -> None:
        signed = TrustedTimeRecord(self.record.state_id, self.record.last_successful_time, 1,
                                   self.integrity.sign(self.record), self.record.last_event_ref)
        self.assertFalse(HmacTrustedTimeIntegrity(Resolver(None), key_ref="synthetic-test-key").verify(signed))
        self.assertFalse(self.integrity.verify(TrustedTimeRecord(signed.state_id, signed.last_successful_time,
                                                                  1, {"algorithm": "none"}, signed.last_event_ref)))
        with self.assertRaises(TrustedTimeError):
            HmacTrustedTimeIntegrity(Resolver(None), key_ref="synthetic-test-key").sign(self.record)

    def test_only_empty_uninitialized_state_is_accepted_without_tag(self) -> None:
        self.assertTrue(self.integrity.verify(TrustedTimeRecord(uuid.uuid4(), None, 0, None, None)))
        self.assertFalse(HmacTrustedTimeIntegrity(
            Resolver(None), key_ref="synthetic-test-key",
        ).verify(TrustedTimeRecord(uuid.uuid4(), None, 0, None, None)))
        self.assertFalse(self.integrity.verify(TrustedTimeRecord(uuid.uuid4(), None, 1, None, None)))


if __name__ == "__main__":
    unittest.main()
