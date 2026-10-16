from __future__ import annotations

import unittest
import uuid
from unittest.mock import Mock

from plm_assistant.modules.jobs.application.ai_provider_test_claim import (
    AIProviderTestClaim, AIProviderTestClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class _Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class ProviderTestClaimTests(unittest.TestCase):
    def setUp(self):
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1, uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), b"p" * 32, 1, 1,
        )
        self.txs = []

        def uow():
            tx = _Tx()
            self.txs.append(tx)
            return tx

        self.repo = Mock(claim_next=Mock(return_value=self.claim),
                         check_current=Mock(return_value=self.claim))
        self.service = AIProviderTestClaims(unit_of_work=uow, repository=self.repo)

    def test_claim_and_checkpoint_are_typed(self):
        self.assertEqual(self.service.claim_next(worker_ref="test-worker", lease_seconds=5), self.claim)
        self.assertTrue(self.txs[-1].committed)
        self.assertEqual(self.service.check_current(object(), job_id=self.claim.job_id,
                                                    fencing_token=1, worker_ref="test-worker"), self.claim)

    def test_invalid_worker_duration_and_repository_result_fail_closed(self):
        for worker, seconds in (("bad worker", 5), ("test-worker", 2), ("test-worker", True)):
            with self.subTest(worker=worker, seconds=seconds), self.assertRaises(JobLeaseError):
                self.service.claim_next(worker_ref=worker, lease_seconds=seconds)
        self.repo.claim_next.return_value = object()
        with self.assertRaises(JobLeaseError):
            self.service.claim_next(worker_ref="test-worker", lease_seconds=5)
        self.assertFalse(self.txs[-1].committed)
        self.repo.check_current.return_value = object()
        with self.assertRaises(JobLeaseError):
            self.service.check_current(object(), job_id=self.claim.job_id,
                                       fencing_token=1, worker_ref="test-worker")

    def test_claim_shape_rejects_non_reference_or_bad_fencing(self):
        for change in ({"policy_sha256": b"short"}, {"fencing_token": 0},
                       {"probe_id": "CUSTOM"}, {"attempt_no": 4}):
            with self.subTest(change=change), self.assertRaises(JobLeaseError):
                AIProviderTestClaim(
                    self.claim.job_id, self.claim.provider_id, self.claim.config_id,
                    self.claim.config_version, self.claim.secret_version_id,
                    self.claim.actor_id, self.claim.trace_id,
                    change.get("policy_sha256", self.claim.policy_sha256),
                    change.get("fencing_token", 1), change.get("attempt_no", 1),
                    change.get("probe_id", "CHAT_CONNECTIVITY_V1"),
                )


if __name__ == "__main__":
    unittest.main()
