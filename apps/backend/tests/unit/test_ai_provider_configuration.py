from __future__ import annotations

import unittest
import uuid
from dataclasses import FrozenInstanceError, replace

from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability,
    ProviderConfiguration,
    ProviderConfigurationError,
    ProviderKind,
)
class AIProviderConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ProviderConfiguration(
            provider_id=uuid.uuid4(),
            config_version=1,
            kind=ProviderKind.OPENAI_COMPATIBLE,
            display_name="北京适配器",
            endpoint_policy_ref="endpoint.cn_beijing.v1",
            secret_ref=uuid.uuid4(),
            data_region="cn-beijing",
            egress_class="EXTERNAL_APPROVAL_REQUIRED",
            capabilities=frozenset({ProviderCapability.CHAT, ProviderCapability.EMBEDDING}),
        )

    def test_all_frozen_provider_kinds_and_capabilities(self) -> None:
        self.assertEqual({item.value for item in ProviderKind}, {
            "OPENAI_COMPATIBLE", "ANTHROPIC_MESSAGES", "GEMINI_NATIVE", "CUSTOM",
        })
        self.assertEqual({item.value for item in ProviderCapability}, {
            "CHAT", "STRUCTURED_OUTPUT", "EMBEDDING", "RERANK",
        })
        for kind in ProviderKind:
            with self.subTest(kind=kind):
                self.assertEqual(replace(self.config, kind=kind).kind, kind)

    def test_configuration_is_versioned_and_immutable(self) -> None:
        self.assertEqual(replace(self.config, config_version=2).config_version, 2)
        with self.assertRaises(FrozenInstanceError):
            self.config.config_version = 2  # type: ignore[misc]

    def test_invalid_identity_version_kind_and_secret_ref_fail_closed(self) -> None:
        for change in (
            {"provider_id": uuid.UUID(int=0)}, {"provider_id": "bad"},
            {"config_version": 0}, {"config_version": True},
            {"kind": "OPENAI_COMPATIBLE"},
            {"secret_ref": None}, {"secret_ref": str(uuid.uuid4())},
            {"secret_ref": uuid.UUID(int=0)},
        ):
            with self.subTest(change=change), self.assertRaises(ProviderConfigurationError):
                replace(self.config, **change)

    def test_raw_endpoint_secret_like_policy_and_invalid_metadata_rejected(self) -> None:
        for change in (
            {"endpoint_policy_ref": "https://example.invalid/v1"},
            {"endpoint_policy_ref": "  endpoint.cn_beijing.v1"},
            {"endpoint_policy_ref": ""},
            {"display_name": ""}, {"display_name": "  adapter"},
            {"display_name": "adapter\nname"},
            {"data_region": "CN Beijing"}, {"data_region": ""},
            {"egress_class": "external"}, {"egress_class": ""},
            {"capabilities": frozenset()},
            {"capabilities": frozenset({"CHAT"})},
            {"capabilities": {ProviderCapability.CHAT}},
        ):
            with self.subTest(change=change), self.assertRaises(ProviderConfigurationError):
                replace(self.config, **change)

    def test_safe_error_does_not_echo_input(self) -> None:
        with self.assertRaises(ProviderConfigurationError) as caught:
            replace(self.config, endpoint_policy_ref="https://example.invalid/path")
        self.assertNotIn("example.invalid", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
