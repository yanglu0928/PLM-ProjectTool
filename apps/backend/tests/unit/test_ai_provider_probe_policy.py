from __future__ import annotations

import unittest
import uuid
from dataclasses import FrozenInstanceError, replace

from plm_assistant.modules.ai.application.probe_policy import (
    EndpointProbePolicy, EndpointProbeRegistry, ProviderProbePlan,
    ProbePolicyError, PROBE_ID, PROBE_TEXT,
)
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)


class AIProviderProbePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = EndpointProbePolicy(
            reference="endpoint.synthetic.v1",
            kind=ProviderKind.OPENAI_COMPATIBLE,
            endpoint_url="https://probe.example.test/v1/chat/completions",
            model_key="synthetic-chat",
            data_region="cn-beijing",
            egress_class="EXTERNAL_APPROVAL_REQUIRED",
        )
        self.config = ProviderConfiguration(
            provider_id=uuid.uuid4(), config_version=1,
            kind=ProviderKind.OPENAI_COMPATIBLE,
            display_name="Synthetic Provider", endpoint_policy_ref=self.policy.reference,
            secret_ref=uuid.uuid4(), data_region="cn-beijing",
            egress_class="EXTERNAL_APPROVAL_REQUIRED",
            capabilities=frozenset({ProviderCapability.CHAT}),
        )

    def test_exact_trusted_policy_produces_only_fixed_probe_plan(self) -> None:
        registry = EndpointProbeRegistry({self.policy.reference: self.policy})
        plan = registry.plan(self.config)
        self.assertEqual((plan.provider_id, plan.config_version, plan.secret_ref),
                         (self.config.provider_id, 1, self.config.secret_ref))
        self.assertEqual((plan.endpoint_url, plan.model_key, plan.probe_id, plan.fixed_text),
                         (self.policy.endpoint_url, self.policy.model_key, PROBE_ID, PROBE_TEXT))
        self.assertEqual(plan.fixed_text, "ping")
        with self.assertRaises(FrozenInstanceError):
            plan.endpoint_url = "https://elsewhere.example.test/v1"  # type: ignore[misc]

    def test_unknown_and_mutated_registry_fail_closed(self) -> None:
        mapping = {self.policy.reference: self.policy}
        registry = EndpointProbeRegistry(mapping)
        mapping.clear()
        self.assertEqual(registry.plan(self.config).policy_ref, self.policy.reference)
        with self.assertRaises(ProbePolicyError):
            registry.plan(replace(self.config, endpoint_policy_ref="endpoint.other.v1"))
        for bad in ({}, {"different": self.policy}, {self.policy.reference: object()}):
            with self.subTest(bad=bad), self.assertRaises(ProbePolicyError):
                EndpointProbeRegistry(bad)

    def test_kind_region_egress_and_capability_mismatch_fail_closed(self) -> None:
        registry = EndpointProbeRegistry({self.policy.reference: self.policy})
        for change in (
            {"kind": ProviderKind.CUSTOM}, {"data_region": "cn-shanghai"},
            {"egress_class": "INTERNAL"},
            {"capabilities": frozenset({ProviderCapability.EMBEDDING})},
        ):
            with self.subTest(change=change), self.assertRaises(ProbePolicyError):
                registry.plan(replace(self.config, **change))
        with self.assertRaises(ProbePolicyError):
            registry.plan(object())  # type: ignore[arg-type]

    def test_untrusted_endpoints_never_enter_policy(self) -> None:
        bad_urls = (
            "http://probe.example.test/v1/chat", "https://user:pass@probe.example.test/v1/chat",
            "https://probe.example.test:8443/v1/chat", "https://probe.example.test/v1/chat?key=x",
            "https://probe.example.test/v1/chat#token", "https://127.0.0.1/v1/chat",
            "https://localhost/v1/chat", "https://probe.example.test/../private",
            "https://probe.example.test/v1/%2e%2e/private", "https://probe.example.test\\@other.test/v1/chat",
        )
        for url in bad_urls:
            with self.subTest(url=url), self.assertRaises(ProbePolicyError) as caught:
                replace(self.policy, endpoint_url=url)
            self.assertNotIn(url, str(caught.exception))

    def test_policy_metadata_and_adapter_kind_are_strict(self) -> None:
        for change in (
            {"reference": "https://probe.example.test"}, {"kind": ProviderKind.CUSTOM},
            {"kind": "OPENAI_COMPATIBLE"}, {"model_key": ""},
            {"model_key": "model?api_key=x"}, {"data_region": "CN Beijing"},
            {"egress_class": "external"},
        ):
            with self.subTest(change=change), self.assertRaises(ProbePolicyError):
                replace(self.policy, **change)

    def test_plan_cannot_be_reconstructed_with_arbitrary_target_or_probe(self) -> None:
        plan = EndpointProbeRegistry({self.policy.reference: self.policy}).plan(self.config)
        for change in (
            {"endpoint_url": "http://127.0.0.1/v1/chat"},
            {"probe_id": "CUSTOM_PROMPT"}, {"model_key": "model?key=x"},
            {"secret_ref": uuid.UUID(int=0)}, {"config_version": 0},
        ):
            with self.subTest(change=change), self.assertRaises(ProbePolicyError):
                replace(plan, **change)
        with self.assertRaises(ProbePolicyError):
            ProviderProbePlan(self.config.provider_id, 1, self.policy.reference,
                              self.policy.endpoint_url, self.policy.model_key,
                              self.config.secret_ref, "CUSTOM_PROMPT")


if __name__ == "__main__":
    unittest.main()
