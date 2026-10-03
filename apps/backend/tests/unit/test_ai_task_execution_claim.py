from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim, AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class Repository:
    def __init__(self, value=None, *, fail: bool = False) -> None:
        self.value, self.fail = value, fail

    def check_current(self, transaction, **kwargs):
        del transaction, kwargs
        if self.fail:
            raise RuntimeError("database detail must be hidden")
        return self.value


class AITaskExecutionClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 10, 3, 18, tzinfo=timezone.utc)
        self.claim = AITaskExecutionClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), b"i" * 32, 2, 2, 3,
            now, now + timedelta(minutes=2),
        )

    def test_exact_current_claim_is_returned(self) -> None:
        service = AITaskExecutionClaims(repository=Repository(self.claim))
        result = service.check_current(
            object(), job_id=self.claim.job_id,
            fencing_token=self.claim.fencing_token, worker_ref="ai-worker-01",
        )
        self.assertIs(result, self.claim)
        self.assertNotIn("input_fingerprint", repr(result))

    def test_mismatched_or_untrusted_claim_fails_closed(self) -> None:
        for repository in (
            Repository(None),
            Repository(replace(self.claim, job_id=uuid.uuid4())),
            Repository(replace(self.claim, fencing_token=3)),
            Repository(fail=True),
        ):
            with self.subTest(repository=repository), self.assertRaises(JobLeaseError):
                AITaskExecutionClaims(repository=repository).check_current(
                    object(), job_id=self.claim.job_id,
                    fencing_token=self.claim.fencing_token,
                    worker_ref="ai-worker-01",
                )

    def test_shape_and_checkpoint_are_strict(self) -> None:
        for changes in (
            {"input_fingerprint": b"short"},
            {"attempt_no": 4},
            {"max_attempts": 11},
            {"lease_expires_at": self.claim.observed_at},
            {"observed_at": self.claim.lease_expires_at},
        ):
            with self.subTest(changes=changes), self.assertRaises(JobLeaseError):
                replace(self.claim, **changes)
        service = AITaskExecutionClaims(repository=Repository(self.claim))
        for job_id, token, worker in (
            (uuid.UUID(int=0), self.claim.fencing_token, "ai-worker-01"),
            (self.claim.job_id, 0, "ai-worker-01"),
            (self.claim.job_id, self.claim.fencing_token, "bad worker"),
        ):
            with self.subTest(job_id=job_id, token=token, worker=worker), self.assertRaises(
                    JobLeaseError):
                service.check_current(
                    object(), job_id=job_id, fencing_token=token, worker_ref=worker,
                )


if __name__ == "__main__":
    unittest.main()
