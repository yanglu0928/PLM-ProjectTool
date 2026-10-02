from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from plm_assistant.entrypoints.ai_probe_policy import (
    DeploymentAIProbePolicyError, create_deployment_ai_probe_registry,
)
from plm_assistant.modules.ai.application.probe_policy import ProbePolicyError
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderConfiguration, ProviderKind,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapConfigurationError, BootstrapSettings, load_bootstrap_settings,
)


class DeploymentAIProbePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.path = self.root / "bootstrap.yaml"
        self.policy = {
            "reference": "endpoint.synthetic.v1", "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://probe.example.test/v1/chat/completions",
            "model_key": "synthetic-chat", "data_region": "cn-beijing",
            "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
        }

    def settings(self, policies):
        with patch.dict(os.environ, {}, clear=True):
            return BootstrapSettings(data_root=self.root, ai_probe_policies=policies)

    def test_missing_fails_closed(self):
        with self.assertRaises(DeploymentAIProbePolicyError) as caught:
            create_deployment_ai_probe_registry(self.settings(()))
        self.assertEqual(str(caught.exception), "AI Provider probe policy unavailable")

    def test_yaml_source_exact_registry_and_fixed_probe(self):
        self.path.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'ai_probe_policies:\n'
            '  - reference: endpoint.synthetic.v1\n'
            '    kind: OPENAI_COMPATIBLE\n'
            '    endpoint_url: https://probe.example.test/v1/chat/completions\n'
            '    model_key: synthetic-chat\n'
            '    data_region: cn-beijing\n'
            '    egress_class: EXTERNAL_APPROVAL_REQUIRED\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            settings = load_bootstrap_settings(self.path)
        registry = create_deployment_ai_probe_registry(settings)
        config = ProviderConfiguration(
            uuid.uuid4(), 1, ProviderKind.OPENAI_COMPATIBLE,
            "Synthetic Provider", self.policy["reference"], uuid.uuid4(),
            "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
            frozenset({ProviderCapability.CHAT}),
        )
        plan = registry.plan(config)
        self.assertEqual(plan.endpoint_url, self.policy["endpoint_url"])
        self.assertEqual(plan.fixed_text, "ping")
        with self.assertRaises(ProbePolicyError):
            registry.plan(ProviderConfiguration(
                config.provider_id, 2, config.kind, config.display_name,
                "other.policy", config.secret_ref, config.data_region,
                config.egress_class, config.capabilities,
            ))

    def test_duplicate_extra_secret_and_unbounded_shape_rejected(self):
        for policies in (
            (self.policy, self.policy),
            ({**self.policy, "api_key": "synthetic-forbidden"},),
            ({key: value for key, value in self.policy.items() if key != "model_key"},),
            tuple({**self.policy, "reference": f"policy.{i}"} for i in range(17)),
            ({**self.policy, "kind": 1},),
        ):
            with self.subTest(policies=len(policies)):
                with self.assertRaises(ValueError):
                    self.settings(policies)

    def test_unsafe_policy_and_kind_fail_without_value_disclosure(self):
        for changed in (
            {"endpoint_url": "http://untrusted.example.test/v1/chat/completions"},
            {"endpoint_url": "https://user:pass@probe.example.test/v1/chat/completions"},
            {"kind": "CUSTOM"},
            {"egress_class": "bad class"},
        ):
            with self.subTest(changed=tuple(changed)):
                settings = self.settings(({**self.policy, **changed},))
                with self.assertRaises(DeploymentAIProbePolicyError) as caught:
                    create_deployment_ai_probe_registry(settings)
                self.assertEqual(str(caught.exception), "AI Provider probe policy unavailable")

    def test_duplicate_yaml_field_rejected_and_no_secret_logged(self):
        self.path.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'ai_probe_policies:\n'
            '  - reference: first.policy\n'
            '    reference: second.policy\n', encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError) as caught:
                load_bootstrap_settings(self.path)
        self.assertEqual(str(caught.exception), "invalid bootstrap configuration")


if __name__ == "__main__":
    unittest.main()
