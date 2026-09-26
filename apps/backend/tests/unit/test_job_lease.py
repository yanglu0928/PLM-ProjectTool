from __future__ import annotations

import unittest

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService


class _UnusedRepository:
    def claim_next(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")


class JobLeaseValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = JobLeaseService(unit_of_work=lambda: None,
                                       repository=_UnusedRepository())

    def test_rejects_invalid_worker_before_transaction(self) -> None:
        for worker in ("", " worker", "worker ", "w" * 129):
            with self.subTest(worker=worker[:12]), self.assertRaises(JobLeaseError):
                self.service.claim_next(worker_ref=worker, lease_seconds=30)

    def test_rejects_invalid_lease_duration_before_transaction(self) -> None:
        for seconds in (0, 3601):
            with self.subTest(seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next(worker_ref="worker-1", lease_seconds=seconds)


if __name__ == "__main__":
    unittest.main()
