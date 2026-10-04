from __future__ import annotations

import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.ai.application.activate_provider import (
    AIProviderActivationError, AIProviderActivationService, ActivateAIProvider,
    ActivatedAIProvider,
)
from plm_assistant.modules.ai.application.provider_activation_proof import ProviderActivationProof
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class ProviderActivationTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.provider, self.config, self.secret = (uuid4() for _ in range(4))
        self.probe, self.job, self.trace, self.audit_id = (uuid4() for _ in range(4))
        self.proof_value = ProviderActivationProof(self.provider, self.config,
            self.secret, self.probe, self.job, 0, "CONFIGURED")
        self.tx = Mock()
        @contextmanager
        def uow():
            yield self.tx
        self.access = Mock(authorized_admin=Mock(return_value=self.actor))
        self.guard = Mock()
        self.proof = Mock(require_locked=Mock(return_value=self.proof_value))
        self.repo = Mock(activate=Mock(return_value=1), get=Mock(return_value=None))
        self.receipts = Mock(reserve=Mock(return_value=None))
        self.audit = Mock(append=Mock(return_value=self.audit_id))
        self.service = AIProviderActivationService(unit_of_work=uow,
            access=self.access, license_guard=self.guard, proof=self.proof,
            repository=self.repo, receipts=self.receipts, audit=self.audit,
            clock=lambda: datetime.now(timezone.utc))
        self.command = ActivateAIProvider(b"s" * 32, b"c" * 32, self.trace,
            self.provider, 0, "synthetic-key-123456")

    def expect(self, code):
        with self.assertRaises(AIProviderActivationError) as cm:
            self.service.activate(self.command)
        self.assertEqual(cm.exception.code, code)
        self.tx.commit.assert_not_called()

    def test_atomic_fresh_activation_and_safe_result(self):
        result = self.service.activate(self.command)
        self.assertEqual((result.provider_id, result.config_id, result.proof_result_id,
                          result.state, result.lock_version, result.etag),
                         (self.provider, self.config, self.probe, "ACTIVE", 1, '"v1"'))
        self.proof.require_locked.assert_called_once_with(self.tx,
            provider_id=self.provider, trace_id=self.trace)
        self.repo.activate.assert_called_once_with(self.tx, proof=self.proof_value,
                                                    expected_lock_version=0)
        self.repo.save.assert_called_once_with(self.tx, result=result)
        self.assertEqual(self.audit.append.call_args.args[0], self.tx)
        self.assertEqual(self.audit.append.call_args.args[1].action, "AI_PROVIDER_ACTIVATED")
        completed = self.receipts.complete.call_args.kwargs["result"]
        self.assertEqual(completed, IdempotencyResult(
            "V1_AI_PROVIDER_ACTIVATE", result.activation_result_id, 200))
        self.assertEqual(self.guard.require_valid.call_count, 2)
        self.assertEqual(self.access.authorized_admin.call_count, 2)
        self.tx.commit.assert_called_once_with()
        self.assertNotIn("session_token", repr(self.command))

    def test_replay_uses_original_snapshot_without_second_write(self):
        original = ActivatedAIProvider(uuid4(), self.provider, self.config,
            self.probe, self.actor, self.audit_id, self.trace, "CONFIGURED", 0, 1)
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_AI_PROVIDER_ACTIVATE", original.activation_result_id, 200)
        self.repo.get.return_value = original
        assert self.service.activate(self.command) == original
        self.repo.get.assert_called_once_with(self.tx, result_id=original.activation_result_id,
            provider_id=self.provider, actor_id=self.actor, expected_lock_version=0)
        self.proof.require_locked.assert_not_called()
        self.repo.activate.assert_not_called()
        self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called()
        self.tx.commit.assert_not_called()

    def test_authority_version_state_and_license_fail_closed(self):
        self.access.authorized_admin.return_value = None
        self.expect("AUTH_ACCESS_DENIED")
        self.receipts.reserve.assert_not_called()
        self.access.authorized_admin.return_value = self.actor
        self.guard.require_valid.side_effect = RuntimeLicenseError("LICENSE_EXPIRED")
        self.expect("LICENSE_OPERATION_DENIED")
        self.guard.require_valid.side_effect = None
        self.proof.require_locked.return_value = replace(self.proof_value, lock_version=1)
        self.expect("CONFLICT_VERSION")
        self.proof.require_locked.return_value = replace(self.proof_value, state="ACTIVE")
        self.expect("AI_PROVIDER_STATE_CONFLICT")
        self.repo.activate.assert_not_called()

    def test_audit_receipt_and_snapshot_failures_rollback(self):
        for target, error in ((self.repo.activate, RuntimeError("sql")),
                              (self.audit.append, RuntimeError("audit")),
                              (self.repo.save, RuntimeError("snapshot")),
                              (self.receipts.complete, RuntimeError("receipt"))):
            with self.subTest(target=target):
                target.side_effect = error
                self.expect("AI_PROVIDER_UNAVAILABLE")
                target.side_effect = None
        self.tx.commit.assert_not_called()

    def test_bad_command_and_tampered_replay(self):
        self.command = replace(self.command, expected_lock_version=True)
        self.expect("VALIDATION_FAILED")
        self.command = replace(self.command, expected_lock_version=0)
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_AI_PROVIDER_ACTIVATE", uuid4(), 200)
        self.expect("AI_PROVIDER_UNAVAILABLE")
        self.proof.require_locked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
