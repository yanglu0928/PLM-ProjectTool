from __future__ import annotations

import unittest
from datetime import datetime, timezone

from plm_assistant.modules.jobs.application.lease import (
    ClosedJobAttempt, JobLeaseError,
)


class ClosedJobAttemptTests(unittest.TestCase):
    def test_accepts_closed_expired_generation(self) -> None:
        value = ClosedJobAttempt(1, 2, "EXPIRED",
                                 datetime.now(timezone.utc), "LEASE_EXPIRED")
        self.assertEqual(value.attempt_no, 1)

    def test_rejects_unfinished_or_unsafe_history(self) -> None:
        now = datetime.now(timezone.utc)
        for args in ((0, 1, "EXPIRED", now, "LEASE_EXPIRED"),
                     (1, 1, "ACTIVE", now, "LEASE_EXPIRED"),
                     (1, 1, "EXPIRED", now, "message with path"),
                     (1, 1, "EXPIRED", now.replace(tzinfo=None), "LEASE_EXPIRED")):
            with self.subTest(args=args), self.assertRaises(JobLeaseError):
                ClosedJobAttempt(*args)


if __name__ == "__main__":
    unittest.main()
