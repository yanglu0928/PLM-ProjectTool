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

    def claim_next_rag_retrieval(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")

    def claim_next_output(self, *args, **kwargs):
        raise AssertionError("invalid command reached repository")


class _ClaimRepository:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def check_output_claim(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.result


class JobLeaseTransactionScopeTests(unittest.TestCase):
    def test_output_claim_can_be_checked_in_the_caller_transaction(self) -> None:
        expected = ClaimedJob(
            uuid.uuid4(), "OUTPUT_GENERATE", "PROJECT", uuid.uuid4(),
            {}, str(uuid.uuid4()), 4, 1,
        )
        repository = _ClaimRepository(expected)
        service = JobLeaseService(
            unit_of_work=lambda: (_ for _ in ()).throw(
                AssertionError("nested UnitOfWork must not be opened")
            ),
            repository=repository,
        )
        transaction = object()

        actual = service.check_output_claim_in_transaction(
            transaction, job_id=expected.job_id,
            fencing_token=expected.fencing_token, worker_ref="worker-1",
        )

        self.assertIs(actual, expected)
        self.assertEqual(len(repository.calls), 1)
        self.assertIs(repository.calls[0][0], transaction)

    def test_invalid_transaction_scoped_claim_never_reaches_repository(self) -> None:
        repository = _ClaimRepository(None)
        service = JobLeaseService(unit_of_work=lambda: None, repository=repository)
        for job_id, fencing_token, worker_ref in (
            (uuid.uuid4(), 1, ""),
            (uuid.UUID(int=0), 1, "worker-1"),
            (uuid.uuid4(), 0, "worker-1"),
        ):
            with self.subTest(worker=worker_ref, token=fencing_token), self.assertRaises(JobLeaseError):
                service.check_output_claim_in_transaction(
                    object(), job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
        self.assertEqual(repository.calls, [])


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

    def test_rag_retrieval_claim_rejects_invalid_input_before_transaction(self) -> None:
        for worker, seconds in (("", 180), ("worker", 0), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next_rag_retrieval(worker_ref=worker,
                                                      lease_seconds=seconds)

    def test_output_claim_rejects_invalid_input_before_transaction(self) -> None:
        for worker, seconds in (("", 60), ("worker", 0), ("worker", 3601)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next_output(worker_ref=worker,
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
