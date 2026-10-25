from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry
from plm_assistant.modules.ai.application.submit_provider_test import (
    AIProviderTestSubmitError, AIProviderTestSubmitService, CurrentProviderTestSource,
    SubmitAIProviderTest,
)
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobRef
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class _Tx:
    def __init__(self):
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.commits += 1


class ProviderTestSubmitTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid.uuid4()
        self.provider = uuid.uuid4()
        self.secret = uuid.uuid4()
        self.config_id = uuid.uuid4()
        config = ProviderConfiguration(
            self.provider, 2, ProviderKind.OPENAI_COMPATIBLE, "Synthetic",
            "trusted.synthetic", self.secret, "cn-beijing", "SYNTHETIC",
            frozenset({ProviderCapability.CHAT}),
        )
        self.current = CurrentProviderTestSource(self.config_id, 3, "CONFIGURED", config)
        self.policy = EndpointProbeRegistry({"trusted.synthetic": EndpointProbePolicy(
            "trusted.synthetic", ProviderKind.OPENAI_COMPATIBLE,
            "https://probe.example.test/v1/chat", "synthetic-chat",
            "cn-beijing", "SYNTHETIC",
        )})
        self.command = SubmitAIProviderTest(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.provider, 3,
            "synthetic-key-0001",
        )
        self.txs = []

        def uow():
            tx = _Tx()
            self.txs.append(tx)
            return tx

        self.access = Mock(authorized_admin=Mock(return_value=self.actor))
        self.guard = Mock(require_valid=Mock())
        self.source = Mock(lock_current=Mock(return_value=self.current))
        self.secret_proof = Mock(active_provider_key_version=Mock(return_value=uuid.uuid4()))
        self.ref = AIProviderTestJobRef(uuid.uuid4(), uuid.uuid4())
        self.queue = Mock(enqueue=Mock(return_value=self.ref),
                          find_by_job=Mock(return_value=self.ref))
        self.receipts = Mock(reserve=Mock(return_value=None), complete=Mock())
        self.audit = Mock(append=Mock())
        self.service = AIProviderTestSubmitService(
            unit_of_work=uow, access=self.access, license_guard=self.guard,
            source=self.source, secret_proof=self.secret_proof,
            probe_registry=self.policy, queue=self.queue, receipts=self.receipts,
            audit=self.audit,
        )

    def test_new_request_binds_current_config_secret_and_audits_once(self):
        self.assertEqual(self.service.submit(self.command), self.ref)
        request = self.queue.enqueue.call_args.kwargs["request"]
        self.assertEqual(request.config_id, self.config_id)
        self.assertEqual(request.config_version, 2)
        self.assertEqual(request.secret_version_id,
                         self.secret_proof.active_provider_key_version.return_value)
        self.assertEqual(len(request.policy_sha256), 32)
        self.assertEqual(request.actor_id, self.actor)
        self.assertEqual(self.txs[0].commits, 0)
        self.assertEqual(self.txs[1].commits, 1)
        self.audit.append.assert_called_once()
        result = self.receipts.complete.call_args.kwargs["result"]
        self.assertEqual(result, IdempotencyResult("V1_AI_PROVIDER_TEST", self.ref.job_id, 202))

    def test_replay_preserves_original_without_new_policy_or_secret_probe(self):
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_AI_PROVIDER_TEST", self.ref.job_id, 202,
        )
        self.assertEqual(self.service.submit(self.command), self.ref)
        self.source.lock_current.assert_not_called()
        self.secret_proof.active_provider_key_version.assert_not_called()
        self.queue.enqueue.assert_not_called()
        self.audit.append.assert_not_called()
        self.assertEqual(sum(tx.commits for tx in self.txs), 0)

    def test_conflict_state_and_secret_fail_closed(self):
        for current, secret_version, error in (
            (replace(self.current, lock_version=4), uuid.uuid4(), "CONFLICT_VERSION"),
            (replace(self.current, state="RETIRED"), uuid.uuid4(), "AI_PROVIDER_STATE_CONFLICT"),
            (self.current, None, "AI_PROVIDER_SECRET_UNAVAILABLE"),
        ):
            with self.subTest(error=error):
                self.source.lock_current.return_value = current
                self.secret_proof.active_provider_key_version.return_value = secret_version
                with self.assertRaises(AIProviderTestSubmitError) as caught:
                    self.service.submit(self.command)
                self.assertEqual(caught.exception.code, error)
        self.queue.enqueue.assert_not_called()
        self.audit.append.assert_not_called()
        self.assertEqual(sum(tx.commits for tx in self.txs), 0)

    def test_authorization_and_audit_failure_never_commit(self):
        self.access.authorized_admin.return_value = None
        with self.assertRaises(AIProviderTestSubmitError) as caught:
            self.service.submit(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.guard.require_valid.assert_not_called()
        self.access.authorized_admin.return_value = self.actor
        self.audit.append.side_effect = RuntimeError("synthetic write failure")
        with self.assertRaises(AIProviderTestSubmitError) as caught:
            self.service.submit(self.command)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_UNAVAILABLE")
        self.assertEqual(sum(tx.commits for tx in self.txs), 0)

    def test_request_shape_and_replay_pair_validation(self):
        with self.assertRaises(AIProviderTestSubmitError) as caught:
            self.service.submit(replace(self.command, expected_lock_version=True))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_AI_PROVIDER_TEST", self.ref.job_id, 202,
        )
        self.queue.find_by_job.return_value = None
        with self.assertRaises(AIProviderTestSubmitError) as caught:
            self.service.submit(self.command)
        self.assertEqual(caught.exception.code, "AI_PROVIDER_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
