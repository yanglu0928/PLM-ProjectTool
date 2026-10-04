from __future__ import annotations

import unittest

from plm_assistant.modules.jobs.application.outbox import OutboxDeliveryError, OutboxDeliveryService


class _UnusedRepository:
    def claim_next(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")


class OutboxDeliveryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OutboxDeliveryService(unit_of_work=lambda: None,
                                             repository=_UnusedRepository())

    def test_rejects_invalid_owner_and_duration(self) -> None:
        for owner in ("", " owner", "owner ", "o" * 129):
            with self.subTest(owner=owner[:12]), self.assertRaises(OutboxDeliveryError):
                self.service.claim_next(owner_ref=owner, lease_seconds=30)
        for seconds in (0, 3601):
            with self.subTest(seconds=seconds), self.assertRaises(OutboxDeliveryError):
                self.service.claim_next(owner_ref="worker-1", lease_seconds=seconds)


if __name__ == "__main__":
    unittest.main()
