from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.jobs.application.lease import (
    ClaimedJob, JobLeaseError, JobLeaseService, ParserLeasePulse,
)


class _UnusedRepository:
    def claim_next(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")

    def claim_next_parse(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")

    def claim_next_ai_task(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")

    def claim_next_rag_build(self, *args, **kwargs):
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

    def test_parse_claim_rejects_invalid_input_before_transaction(self) -> None:
        for worker, seconds in (("", 60), ("worker", 0), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next_parse(worker_ref=worker,
                                              lease_seconds=seconds)

    def test_ai_task_claim_rejects_invalid_input_before_transaction(self) -> None:
        for worker, seconds in (("", 180), ("worker", 0), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next_ai_task(worker_ref=worker,
                                                lease_seconds=seconds)

    def test_rag_build_claim_rejects_invalid_input_before_transaction(self) -> None:
        for worker, seconds in (("", 180), ("worker", 0), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next_rag_build(worker_ref=worker,
                                                  lease_seconds=seconds)

    def test_parse_pulse_rejects_invalid_input_before_transaction(self) -> None:
        for worker, seconds in (("", 60), ("worker", 0), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.pulse_parse(job_id=uuid.uuid4(), fencing_token=1,
                                         worker_ref=worker, lease_seconds=seconds)

    def test_parse_pulse_rejects_other_job_type(self) -> None:
        claim = ClaimedJob(uuid.uuid4(), "AUDIT_EXPORT", "PROJECT", uuid.uuid4(),
                           {}, str(uuid.uuid4()), 1, 1)
        with self.assertRaises(JobLeaseError):
            ParserLeasePulse(claim, "RUNNING")


if __name__ == "__main__":
    unittest.main()
