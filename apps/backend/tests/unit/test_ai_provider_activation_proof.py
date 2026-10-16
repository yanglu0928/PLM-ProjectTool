from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry, probe_policy_sha256
from plm_assistant.modules.ai.application.provider_activation_proof import (
    LatestProviderProbe, ProviderActivationProofError, ProviderActivationProofService,
)
from plm_assistant.modules.ai.application.submit_provider_test import CurrentProviderTestSource
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class ProviderActivationProofTests(unittest.TestCase):
    def setUp(self):
        self.provider, self.config_id, self.secret_ref, self.secret_version = (uuid4() for _ in range(4))
        self.trace, self.job, self.result = uuid4(), uuid4(), uuid4()
        self.config = ProviderConfiguration(self.provider, 1, ProviderKind.OPENAI_COMPATIBLE,
            "Synthetic Provider", "endpoint.synthetic.v1", self.secret_ref,
            "cn-beijing", "SYNTHETIC", frozenset({ProviderCapability.CHAT}))
        self.current = CurrentProviderTestSource(self.config_id, 0, "CONFIGURED", self.config)
        self.policies = EndpointProbeRegistry({"endpoint.synthetic.v1": EndpointProbePolicy(
            "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
            "https://probe.example.test/v1/chat", "synthetic-chat", "cn-beijing", "SYNTHETIC")})
        digest = probe_policy_sha256(self.config, self.policies.plan(self.config))
        self.latest_proof = LatestProviderProbe(self.provider, self.config_id,
            self.secret_version, self.job, self.result, digest)
        self.source = Mock(lock_current=Mock(return_value=self.current))
        self.secrets = Mock(active_provider_key_version=Mock(return_value=self.secret_version))
        self.latest = Mock(latest_success=Mock(return_value=self.latest_proof))
        self.guard = Mock()
        self.service = ProviderActivationProofService(current=self.source, secrets=self.secrets,
            policies=self.policies, latest=self.latest, license_guard=self.guard)
        self.tx = Mock()

    def require(self):
        return self.service.require_locked(self.tx, provider_id=self.provider, trace_id=self.trace)

    def expect(self, code):
        with self.assertRaises(ProviderActivationProofError) as cm:
            self.require()
        self.assertEqual(cm.exception.code, code)
        self.tx.commit.assert_not_called()

    def test_current_success_is_only_an_internal_same_uow_snapshot(self):
        proof = self.require()
        self.assertEqual((proof.provider_id, proof.config_id, proof.secret_version_id,
                          proof.result_id, proof.job_id, proof.lock_version, proof.state),
                         (self.provider, self.config_id, self.secret_version,
                          self.result, self.job, 0, "CONFIGURED"))
        self.source.lock_current.assert_called_once_with(self.tx, provider_id=self.provider)
        self.secrets.active_provider_key_version.assert_called_once_with(self.tx,
                                                                          secret_ref=self.secret_ref)
        self.latest.latest_success.assert_called_once_with(self.tx, provider_id=self.provider)
        self.assertEqual(self.guard.require_valid.call_count, 2)
        self.tx.commit.assert_not_called()
        self.assertNotIn(self.latest_proof.policy_sha256.hex(), repr(self.latest_proof))

    def test_old_config_secret_or_policy_proof_rejected(self):
        for change in ({"config_id": uuid4()}, {"secret_version_id": uuid4()},
                       {"policy_sha256": b"x" * 32}, {"provider_id": uuid4()}):
            with self.subTest(change=change):
                self.latest.latest_success.return_value = replace(self.latest_proof, **change)
                self.expect("AI_PROVIDER_TEST_REQUIRED")
        self.latest.latest_success.return_value = self.latest_proof
        self.secrets.active_provider_key_version.return_value = uuid4()
        self.expect("AI_PROVIDER_TEST_REQUIRED")
        self.secrets.active_provider_key_version.return_value = None
        self.expect("AI_PROVIDER_SECRET_UNAVAILABLE")

    def test_missing_failure_and_retired_proof_rejected(self):
        self.latest.latest_success.return_value = None
        self.expect("AI_PROVIDER_TEST_REQUIRED")
        self.source.lock_current.return_value = replace(self.current, state="RETIRED")
        self.expect("AI_PROVIDER_STATE_CONFLICT")
        self.source.lock_current.return_value = None
        self.expect("AI_PROVIDER_NOT_FOUND")

    def test_changed_policy_and_license_fail_closed(self):
        changed = EndpointProbeRegistry({"endpoint.synthetic.v1": EndpointProbePolicy(
            "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
            "https://changed.example.test/v1/chat", "synthetic-chat", "cn-beijing", "SYNTHETIC")})
        altered = ProviderActivationProofService(current=self.source, secrets=self.secrets,
            policies=changed, latest=self.latest, license_guard=self.guard)
        with self.assertRaises(ProviderActivationProofError) as cm:
            altered.require_locked(self.tx, provider_id=self.provider, trace_id=self.trace)
        self.assertEqual(cm.exception.code, "AI_PROVIDER_TEST_REQUIRED")
        self.guard.require_valid.side_effect = RuntimeLicenseError("LICENSE_EXPIRED")
        self.expect("LICENSE_OPERATION_DENIED")

    def test_bad_input_and_repository_exception_are_sanitized(self):
        with self.assertRaises(ProviderActivationProofError) as cm:
            self.service.require_locked(self.tx, provider_id=uuid4(), trace_id=None)
        self.assertEqual(cm.exception.code, "VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called()
        self.latest.latest_success.side_effect = RuntimeError("private SQL or key")
        self.expect("AI_PROVIDER_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
