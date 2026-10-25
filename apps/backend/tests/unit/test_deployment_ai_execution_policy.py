from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plm_assistant.entrypoints.ai_execution_policy import (
    DeploymentAIExecutionPolicyError,
    create_deployment_ai_execution_registry,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)


class DeploymentAIExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.policy = {
            "reference": "endpoint.business.v1",
            "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://business.example.test/v1/chat/completions",
            "data_region": "cn-beijing",
            "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
            "allowed_model_keys": ["business-chat"],
            "max_response_bytes": 1048576,
            "connect_timeout_seconds": 5,
            "read_timeout_seconds": 30,
            "total_timeout_seconds": 40,
        }

    def settings(self, policies):
        with patch.dict(os.environ, {}, clear=True):
            return BootstrapSettings(
                data_root=self.root, ai_execution_policies=policies,
            )

    def test_exact_policy_resolves_only_matching_route(self):
        registry = create_deployment_ai_execution_registry(
            self.settings((self.policy,)),
        )
        resolved = registry.resolve(
            reference=self.policy["reference"],
            provider_kind=ProviderKind.OPENAI_COMPATIBLE,
            data_region="cn-beijing",
            egress_class="EXTERNAL_APPROVAL_REQUIRED",
            provider_model_key="business-chat",
        )
        self.assertEqual(resolved.endpoint_url, self.policy["endpoint_url"])
        self.assertEqual(resolved.total_timeout_seconds, 40)
        with self.assertRaises(AIProviderExecutionError):
            registry.resolve(
                reference=self.policy["reference"],
                provider_kind=ProviderKind.OPENAI_COMPATIBLE,
                data_region="cn-beijing",
                egress_class="EXTERNAL_APPROVAL_REQUIRED",
                provider_model_key="unlisted-model",
            )

    def test_missing_secret_extra_duplicate_and_unbounded_rejected(self):
        for policies in (
            (),
            (self.policy, self.policy),
            ({**self.policy, "api_key": "forbidden"},),
            ({key: value for key, value in self.policy.items()
              if key != "total_timeout_seconds"},),
            ({**self.policy, "allowed_model_keys": []},),
            ({**self.policy, "max_response_bytes": 100_000_001},),
            tuple({**self.policy, "reference": f"policy.{i}"}
                  for i in range(17)),
        ):
            with self.subTest(count=len(policies)):
                if not policies:
                    with self.assertRaises(DeploymentAIExecutionPolicyError):
                        create_deployment_ai_execution_registry(
                            self.settings(policies),
                        )
                else:
                    with self.assertRaises(ValueError):
                        self.settings(policies)

    def test_unsafe_semantics_fail_without_value_disclosure(self):
        for changed in (
            {"endpoint_url": "http://127.0.0.1/v1/chat/completions"},
            {"endpoint_url": "https://user:pass@example.test/v1/chat"},
            {"kind": "CUSTOM"},
            {"connect_timeout_seconds": 50, "total_timeout_seconds": 40},
            {"allowed_model_keys": ["bad model"]},
        ):
            settings = self.settings(({**self.policy, **changed},))
            with self.assertRaises(DeploymentAIExecutionPolicyError) as error:
                create_deployment_ai_execution_registry(settings)
            self.assertEqual(
                str(error.exception),
                "AI Provider execution policy unavailable",
            )


if __name__ == "__main__":
    unittest.main()
