from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.ai.application.probe_policy import (
    EndpointProbePolicy, EndpointProbeRegistry, probe_policy_sha256,
)
from plm_assistant.modules.ai.application.provider_test_preflight import (
    ProviderTestPreflightError, ProviderTestPreflightService,
)
from plm_assistant.modules.ai.application.submit_provider_test import CurrentProviderTestSource
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ProviderTestPreflightTests(unittest.TestCase):
    def setUp(self):
        self.provider_id = uuid.uuid4()
        self.config_id = uuid.uuid4()
        self.secret_ref = uuid.uuid4()
        self.secret_version = uuid.uuid4()
        self.trace = uuid.uuid4()
        self.config = ProviderConfiguration(
            self.provider_id, 2, ProviderKind.OPENAI_COMPATIBLE,
            "Synthetic", "trusted.synthetic", self.secret_ref,
            "cn-beijing", "SYNTHETIC", frozenset({ProviderCapability.CHAT}),
        )
        self.registry = EndpointProbeRegistry({"trusted.synthetic": EndpointProbePolicy(
            "trusted.synthetic", ProviderKind.OPENAI_COMPATIBLE,
            "https://probe.example.test/v1/chat", "synthetic-chat",
            "cn-beijing", "SYNTHETIC",
        )})
        policy = probe_policy_sha256(self.config, self.registry.plan(self.config))
        self.claim = AIProviderTestClaim(
            uuid.uuid4(), self.provider_id, self.config_id, 2,
            self.secret_version, uuid.uuid4(), self.trace, policy, 1, 1,
        )
        self.claims = Mock(check_current=Mock(return_value=self.claim))
        self.guard = Mock(require_valid=Mock())
        self.source = Mock(lock_current=Mock(return_value=CurrentProviderTestSource(
            self.config_id, 0, "CONFIGURED", self.config,
        )))
        self.secret = Mock(active_provider_key_version=Mock(return_value=self.secret_version))
        self.service = ProviderTestPreflightService(
            unit_of_work=_Tx, claims=self.claims, license_guard=self.guard,
            source=self.source, secret_proof=self.secret, probe_registry=self.registry,
        )

    def call(self):
        return self.service.preflight(job_id=self.claim.job_id, fencing_token=1,
                                      worker_ref="probe-worker", trace_id=self.trace)

    def test_matching_snapshot_is_not_network_execution(self):
        snapshot = self.call()
        self.assertEqual(snapshot.claim, self.claim)
        self.assertEqual(snapshot.plan.fixed_text, "ping")
        self.assertEqual(self.guard.require_valid.call_count, 2)
        self.secret.active_provider_key_version.assert_called_once()

    def test_config_policy_secret_and_state_drift_fail_closed(self):
        for current, version, registry, expected in (
            (CurrentProviderTestSource(uuid.uuid4(), 0, "CONFIGURED", self.config),
             self.secret_version, self.registry, "AI_PROVIDER_CONFIG_CHANGED"),
            (CurrentProviderTestSource(self.config_id, 0, "RETIRED", self.config),
             self.secret_version, self.registry, "AI_PROVIDER_CONFIG_CHANGED"),
            (self.source.lock_current.return_value, uuid.uuid4(),
             self.registry, "AI_PROVIDER_SECRET_CHANGED"),
            (self.source.lock_current.return_value, self.secret_version,
             EndpointProbeRegistry({"trusted.synthetic": EndpointProbePolicy(
                 "trusted.synthetic", ProviderKind.OPENAI_COMPATIBLE,
                 "https://changed.example.test/v1/chat", "synthetic-chat",
                 "cn-beijing", "SYNTHETIC",
             )}), "AI_PROVIDER_POLICY_CHANGED"),
        ):
            with self.subTest(expected=expected):
                self.source.lock_current.return_value = current
                self.secret.active_provider_key_version.return_value = version
                self.service._registry = registry
                with self.assertRaises(ProviderTestPreflightError) as caught:
                    self.call()
                self.assertEqual(caught.exception.code, expected)

    def test_stale_fence_trace_and_license_fail_closed(self):
        self.claims.check_current.side_effect = JobLeaseError("STALE_LEASE")
        with self.assertRaises(ProviderTestPreflightError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, "JOB_LEASE_LOST")
        self.claims.check_current.side_effect = None
        self.claims.check_current.return_value = replace(self.claim, trace_id=uuid.uuid4())
        with self.assertRaises(ProviderTestPreflightError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, "JOB_STORE_UNAVAILABLE")
        self.claims.check_current.return_value = self.claim
        self.guard.require_valid.side_effect = RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        with self.assertRaises(ProviderTestPreflightError) as caught:
            self.call()
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")


if __name__ == "__main__":
    unittest.main()
